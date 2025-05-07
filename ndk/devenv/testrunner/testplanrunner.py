# Copyright (C) 2024 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Runs a test plan on a test fleet."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from asyncio import Queue, Task
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import ndk.ansi
from ndk.devenv.devices import Device, DeviceFleet, DeviceShardingGroup
from ndk.test.printers import Printer
from ndk.test.report import Report
from ndk.test.result import Failure, Skipped, TestResult, UnexpectedSuccess

from .testgroup import TestGroup
from .testplan import TestPlan
from .testrun import TestRun
from .ui import TestProgressUi, get_test_progress_ui


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


class DeviceShardingQueue:
    def __init__(self, queues: dict[DeviceShardingGroup, Queue[Device]]) -> None:
        self.queues = queues

    @staticmethod
    async def for_sharding_groups(
        groups: set[DeviceShardingGroup], max_tasks_per_device: int = 4
    ) -> DeviceShardingQueue:
        queues: dict[DeviceShardingGroup, Queue[Device]] = {}
        for group in groups:
            queues[group] = Queue()
            for device in group.devices:
                for _ in range(max_tasks_per_device):
                    await queues[group].put(device)

        return DeviceShardingQueue(queues)

    def get_queue(self, group: DeviceShardingGroup) -> Queue[Device]:
        return self.queues[group]


def report_skipped_tests_for_missing_devices(
    report: Report[DeviceShardingGroup], test_group: TestGroup, fleet: DeviceFleet
) -> None:
    """Records tests with no compatible device as skipped in the test report."""
    for group in fleet.get_missing():
        if not group.config.can_run_build_config(test_group.build_config):
            # These are a configuration that will never be valid, like a minSdkVersion
            # 30 test on an API 21 device. No need to report these.
            continue
        for test_case in test_group.tests:
            report.add_result(
                test_case.build_system,
                Skipped(TestRun(test_case, group), "No devices available"),
            )


def pair_test_runs(
    test_plan: TestPlan, report: Report[DeviceShardingGroup], fleet: DeviceFleet
) -> list[TestRun]:
    """Creates a TestRun object for each device/test case pairing."""
    test_runs = []
    for test_group in test_plan.iter_test_groups():
        if not test_group.has_tests():
            continue

        report_skipped_tests_for_missing_devices(report, test_group, fleet)
        for device_group in fleet.get_unique_device_groups():
            if device_group.can_run_build_config(test_group.build_config):
                test_runs.extend([TestRun(tc, device_group) for tc in test_group.tests])
    return test_runs


async def wait_for_results(
    ui: TestProgressUi,
    report: Report[DeviceShardingGroup],
    tasks: list[Task[tuple[DeviceShardingGroup, TestResult]]],
) -> None:
    with ui.ui_context():
        for task in asyncio.as_completed(tasks):
            device_group, result = await task
            suite = result.test.build_system
            report.add_result(suite, result)
            ui.on_test_finished(device_group, result)
        ui.on_finished()


@asynccontextmanager
async def device_from_queue(queue: Queue[Device]) -> AsyncIterator[Device]:
    device = await queue.get()
    try:
        yield device
    finally:
        await queue.put(device)


async def run_test_on_device(device: Device, test: TestRun) -> TestResult:
    logger().info("Running %s", test.name)
    return await test.run(device)


async def run_test(
    queue: Queue[Device], test: TestRun
) -> tuple[DeviceShardingGroup, TestResult]:
    async with device_from_queue(queue) as device:
        return test.device_group, await run_test_on_device(device, test)


def flake_filter(result: TestResult) -> bool:
    if isinstance(result, UnexpectedSuccess):
        # There are no flaky successes.
        return False

    assert isinstance(result, Failure)

    # adb might return no text at all under high load.
    if "Could not find exit status in shell output." in result.message:
        return True

    return False


async def restart_flaky_tests(
    ui: TestProgressUi, report: Report[DeviceShardingGroup]
) -> list[Task[tuple[DeviceShardingGroup, TestResult]]]:
    """Finds and restarts any failing flaky tests."""
    rerun_tests = report.remove_all_failing_flaky(flake_filter)
    if rerun_tests:
        cooldown = 10
        logger().warning(
            "Found %d flaky failures. Sleeping for %d seconds to let "
            "devices recover.",
            len(rerun_tests),
            cooldown,
        )
        time.sleep(cooldown)

    tasks = []
    for flaky_report in rerun_tests:
        logger().warning("Flaky test failure: %s", flaky_report.result)
        group = flaky_report.result.test.device_group
        tasks.append(asyncio.create_task(run_test(group, flaky_report.result.test)))
        ui.on_test_scheduled(flaky_report.result.test)
    return tasks


async def run_and_collect_logs(
    queue: Queue[Device],
    test_run: TestRun,
) -> tuple[DeviceShardingGroup, TestResult]:
    async with device_from_queue(queue) as device:
        await device.clear_logcat()
        result = await run_test_on_device(device, test_run)
        if not isinstance(result, Failure):
            logger().warning(
                "Failing test passed on re-run while collecting logs. This makes testing "
                "slower. Test flake should be investigated."
            )
            return test_run.device_group, result
        log = await device.logcat()
    result.message += f"\nlogcat contents:\n{log}"
    return test_run.device_group, result


async def get_and_attach_logs_for_failing_tests(
    groups: set[DeviceShardingGroup],
    report: Report[DeviceShardingGroup],
    printer: Printer,
) -> None:
    failures = report.remove_all_true_failures()
    if not failures:
        return

    # Have to use max of one worker per re-run to ensure that the logs we collect do not
    # conflate with other tests.
    queues = await DeviceShardingQueue.for_sharding_groups(
        groups, max_tasks_per_device=1
    )

    console = ndk.ansi.get_console()
    ui = get_test_progress_ui(
        console, printer, log_all_results=logger().isEnabledFor(logging.INFO)
    )

    tasks = []
    for failure in failures:
        tasks.append(
            asyncio.create_task(
                run_and_collect_logs(queues.get_queue(failure.user_data), failure.test)
            )
        )
        ui.on_test_scheduled(failure.test)
    await wait_for_results(ui, report, tasks)


class TestPlanRunner:
    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    async def run(
        self, test_plan: TestPlan, fleet: DeviceFleet
    ) -> Report[DeviceShardingGroup]:
        report = Report[DeviceShardingGroup]()

        groups = fleet.get_unique_device_groups()
        queues = await DeviceShardingQueue.for_sharding_groups(groups)

        # Need an input queue per device group, a single result queue, and a
        # pool of threads per device.

        # Shuffle the test runs to distribute the load more evenly. These are
        # ordered by (build config, device, test), so most of the tests running
        # at any given point in time are all running on the same device.
        test_runs = pair_test_runs(test_plan, report, fleet)
        random.shuffle(test_runs)

        console = ndk.ansi.get_console()
        ui = get_test_progress_ui(
            console,
            self.printer,
            log_all_results=logger().isEnabledFor(logging.INFO),
        )
        tasks = []
        for test_run in test_runs:
            tasks.append(
                asyncio.create_task(
                    run_test(queues.get_queue(test_run.device_group), test_run)
                )
            )
            ui.on_test_scheduled(test_run)

        await wait_for_results(ui, report, tasks)

        ui = get_test_progress_ui(
            console,
            self.printer,
            log_all_results=logger().isEnabledFor(logging.INFO),
        )
        tasks = await restart_flaky_tests(ui, report)
        await wait_for_results(ui, report, tasks)

        await get_and_attach_logs_for_failing_tests(groups, report, self.printer)

        return report
