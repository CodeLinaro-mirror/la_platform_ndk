#
# Copyright (C) 2024 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Runner for device tests."""

import logging
from collections.abc import Iterator
from pathlib import Path

from ndk.test.devices import DeviceFleet, find_devices
from ndk.test.filters import TestFilter
from ndk.test.printers import Printer
from ndk.test.spec import BuildConfiguration, TestSpec
from ndk.timer import TimingReport
from ndk.workqueue import WorkQueue

from .devicepreparer import DevicePreparer
from .testplan import TestPlan
from .testplanrunner import TestPlanRunner


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


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

    def run(self, clean_devices: bool, require_all_devices: bool) -> str | None:
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
        workqueue = WorkQueue()
        try:
            with self.timing_report.timed("Device discovery"):
                fleet = find_devices(self.test_spec.devices, workqueue)

            if require_all_devices:
                if not verify_have_all_requested_devices(fleet):
                    return "Some requested devices were not available."

            for config in iter_configs_with_no_device(self.test_plan, fleet):
                logger().warning("No device found for %s.", config)

            preparer = DevicePreparer(fleet)
            if clean_devices:
                with self.timing_report.timed("Clean device"):
                    preparer.clean(workqueue)

            with self.timing_report.timed("Push"):
                preparer.push(workqueue, self.test_plan)
        finally:
            workqueue.terminate()
            workqueue.join()

        test_runner = TestPlanRunner(self.printer)
        with self.timing_report.timed("Run"):
            report = test_runner.run(self.test_plan, fleet)

        self.printer.print_summary(report)
        return None
