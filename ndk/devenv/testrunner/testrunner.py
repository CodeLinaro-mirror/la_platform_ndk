# Copyright (C) 2024 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Runner for device tests."""

import asyncio
import logging
import shutil
from collections.abc import Iterator
from pathlib import Path

from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

from ndk.abis import Abi
from ndk.devenv.deviceproviders.acid import ACID_PATH, AcidDeviceProvider
from ndk.devenv.devices import Device, DeviceFleet, find_devices
from ndk.ext.subprocess import async_run
from ndk.test.filters import TestFilter
from ndk.test.printers import Printer
from ndk.test.spec import BuildConfiguration, TestSpec
from ndk.timer import TimingReport

from .devicepreparer import DevicePreparer
from .testplan import TestPlan
from .testplanrunner import TestPlanRunner


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


async def gcert_status_is_good() -> bool:
    proc = await async_run(["gcertstatus"], check=False, capture_output=True)
    return proc.returncode == 0


async def acquire_gcert() -> bool:
    proc = await async_run(["gcert"], check=True)
    return proc.returncode == 0


async def acquire_missing_devices(fleet: DeviceFleet) -> None:
    """Attempts to acquire missing devices and add them to the fleet."""

    async def acquire_device_with_progress(
        task_id: TaskID, provider: AcidDeviceProvider, abi: Abi, api: int
    ) -> tuple[TaskID, Device | None]:
        return task_id, await provider.acquire_device(abi, api)

    missing_shards = fleet.get_missing()
    if not missing_shards:
        return

    if shutil.which(ACID_PATH) is None:
        print("Cannot auto-acquire missing devices because acid is not installed")
        return

    if not await gcert_status_is_good():
        print("Running gcert to acquire certificates for acid")
        if not await acquire_gcert():
            print("Unable to acquire credentials, cannot lease device from acid")
            return

    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
    )
    with progress:
        provider = AcidDeviceProvider()
        missing_configs: set[tuple[Abi, int]] = set()
        for shard in missing_shards:
            for abi in shard.config.abis:
                missing_configs.add((abi, shard.config.version))

        tasks = []
        for missing_config in missing_configs:
            abi, api = missing_config
            task_id = progress.add_task(
                f"Leasing android-{api} {abi} from ACID", total=None
            )
            tasks.append(
                asyncio.create_task(
                    acquire_device_with_progress(task_id, provider, abi, api)
                )
            )

        for device_task in asyncio.as_completed(tasks):
            task_id, device = await device_task
            if device is not None:
                fleet.add_device(device)
            progress.update(task_id, completed=True, total=1)


def verify_have_all_requested_devices(fleet: DeviceFleet) -> bool:
    missing_configs = fleet.get_missing()
    if missing_configs:
        logger().warning(
            "Missing device configurations: %s",
            ", ".join(str(c) for c in missing_configs),
        )
        return False
    return True


def iter_configs_with_no_device(
    test_plan: TestPlan, fleet: DeviceFleet
) -> Iterator[BuildConfiguration]:
    for config in test_plan.iter_build_configs():
        if not fleet.can_run_build_config(config):
            yield config


class TestRunner:
    """Discovers, prepares, and runs device tests.

    This is distinct from the similarly named TestPlanRunner in that it does the
    whole task of what a user would consider "running the tests":

    1. Find tests to create a test plan
    2. Prepare test devices
    3. Run the test plan on those devices
    4. Report results

    TestRunner does all of those things, with step 3 delegated to
    TestPlanRunner.
    """

    def __init__(
        self,
        test_spec: TestSpec,
        test_filter: TestFilter,
        printer: Printer,
        timing_report: TimingReport | None = None,
    ) -> None:
        self.test_plan = TestPlan(test_spec, test_filter)
        self.test_spec = test_spec
        self.printer = printer
        if timing_report is None:
            timing_report = TimingReport()
        self.timing_report = timing_report

    def add_tests(self, test_dist: Path, test_src: Path) -> None:
        with self.timing_report.timed("Test discovery"):
            self.test_plan.add_tests_from_dist_dir(test_dist, test_src)

    def has_tests(self) -> bool:
        return self.test_plan.has_tests()

    async def run(self, clean_devices: bool, require_all_devices: bool) -> str | None:
        # For finding devices, we have a list of devices we want to run on in our
        # config file. If we did away with this list, we could instead run every
        # test on every compatible device, but in the event of multiple similar
        # devices, that's a lot of duplication. The list keeps us from running
        # tests on android-24 and android-25, which don't have meaningful
        # differences.
        #
        # The list also makes sure we don't miss any devices that we expect to run
        # on.
        #
        # The other thing we need to verify is that each test we find is run at
        # least once.
        #
        # Get the list of all devices. Prune this by the requested device
        # configuration. For each requested configuration that was not found, print
        # a warning. Then compare that list of devices against all our tests and
        # make sure each test is claimed by at least one device. For each
        # configuration that is unclaimed, print a warning.
        with self.timing_report.timed("Device discovery"):
            fleet = await find_devices(self.test_spec.devices)

        await acquire_missing_devices(fleet)

        if require_all_devices:
            if not verify_have_all_requested_devices(fleet):
                return "Some requested devices were not available."

        for config in iter_configs_with_no_device(self.test_plan, fleet):
            logger().warning("No device found for %s.", config)

        preparer = DevicePreparer(fleet)
        if clean_devices:
            with self.timing_report.timed("Clean device"):
                await preparer.clean()

        with self.timing_report.timed("Push"):
            await preparer.push(self.test_plan)

        test_runner = TestPlanRunner(self.printer)
        with self.timing_report.timed("Run"):
            report = await test_runner.run(self.test_plan, fleet)

        self.printer.print_summary(report)
        return None
