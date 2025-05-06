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
"""Runs a test plan on a test fleet."""
import logging
import random
import time

import ndk.ansi
import ndk.test.ui

# TODO: This module should be moved into ndk.devenv.
from ndk.devenv.devices import Device, DeviceFleet, DeviceShardingGroup
from ndk.test.printers import Printer
from ndk.test.report import Report
from ndk.test.result import Failure, Skipped, TestResult, UnexpectedSuccess
from ndk.workqueue import ShardingWorkQueue, Worker

from .testgroup import TestGroup
from .testplan import TestPlan
from .testrun import TestRun


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


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


def wait_for_results(
    ui: ndk.test.ui.TestProgressUi,
    report: Report[DeviceShardingGroup],
    workqueue: ShardingWorkQueue[tuple[DeviceShardingGroup, TestResult], Device],
) -> None:
    with ui.ui_context():
        while not workqueue.finished():
            results = workqueue.get_results()
            for sharding_group, result in results:
                suite = result.test.build_system
                report.add_result(suite, result)
                ui.on_test_finished(sharding_group, result)
        ui.on_finished()


def run_test(worker: Worker, test: TestRun) -> tuple[DeviceShardingGroup, TestResult]:
    device = worker.data[0]
    worker.status = f"Running {test.name}"
    return test.device_group, test.run(device)


def flake_filter(result: TestResult) -> bool:
    if isinstance(result, UnexpectedSuccess):
        # There are no flaky successes.
        return False

    assert isinstance(result, Failure)

    # adb might return no text at all under high load.
    if "Could not find exit status in shell output." in result.message:
        return True

    return False


def restart_flaky_tests(
    ui: ndk.test.ui.TestProgressUi,
    report: Report[DeviceShardingGroup],
    workqueue: ShardingWorkQueue[tuple[DeviceShardingGroup, TestResult], Device],
) -> None:
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

    for flaky_report in rerun_tests:
        logger().warning("Flaky test failure: %s", flaky_report.result)
        group = flaky_report.result.test.device_group
        workqueue.add_task(group, run_test, flaky_report.result.test)
        ui.on_test_scheduled(flaky_report.result.test)


def run_and_collect_logs(
    worker: Worker, test_run: TestRun
) -> tuple[DeviceShardingGroup, TestResult]:
    device: Device = worker.data[0]
    worker.status = "Clearing device log"
    device.clear_logcat()
    _group, result = run_test(worker, test_run)
    if not isinstance(result, Failure):
        logger().warning(
            "Failing test passed on re-run while collecting logs. This makes testing "
            "slower. Test flake should be investigated."
        )
        return test_run.device_group, result
    worker.status = "Collecting device log"
    log = device.logcat()
    result.message += f"\nlogcat contents:\n{log}"
    return test_run.device_group, result


def get_and_attach_logs_for_failing_tests(
    fleet: DeviceFleet, report: Report[DeviceShardingGroup], printer: Printer
) -> None:
    failures = report.remove_all_true_failures()
    if not failures:
        return

    # Have to use max of one worker per re-run to ensure that the logs we collect do not
    # conflate with other tests.
    queue: ShardingWorkQueue[tuple[DeviceShardingGroup, TestResult], Device] = (
        ShardingWorkQueue(fleet.get_unique_device_groups(), 1)
    )

    console = ndk.ansi.get_console()
    ui = ndk.test.ui.get_test_progress_ui(
        console, printer, log_all_results=logger().isEnabledFor(logging.INFO)
    )

    try:
        for failure in failures:
            queue.add_task(failure.user_data, run_and_collect_logs, failure.test)
            ui.on_test_scheduled(failure.test)
        wait_for_results(ui, report, queue)
    finally:
        queue.terminate()
        queue.join()


class TestPlanRunner:
    def __init__(self, printer: Printer) -> None:
        self.printer = printer

    def run(
        self, test_plan: TestPlan, fleet: DeviceFleet
    ) -> Report[DeviceShardingGroup]:
        report = Report[DeviceShardingGroup]()
        shard_queue: ShardingWorkQueue[
            tuple[DeviceShardingGroup, TestResult], Device
        ] = ShardingWorkQueue(fleet.get_unique_device_groups(), 4)
        try:
            # Need an input queue per device group, a single result queue, and a
            # pool of threads per device.

            # Shuffle the test runs to distribute the load more evenly. These are
            # ordered by (build config, device, test), so most of the tests running
            # at any given point in time are all running on the same device.
            test_runs = pair_test_runs(test_plan, report, fleet)
            random.shuffle(test_runs)

            console = ndk.ansi.get_console()
            ui = ndk.test.ui.get_test_progress_ui(
                console,
                self.printer,
                log_all_results=logger().isEnabledFor(logging.INFO),
            )
            for test_run in test_runs:
                shard_queue.add_task(test_run.device_group, run_test, test_run)
                ui.on_test_scheduled(test_run)

            wait_for_results(ui, report, shard_queue)

            ui = ndk.test.ui.get_test_progress_ui(
                console,
                self.printer,
                log_all_results=logger().isEnabledFor(logging.INFO),
            )
            restart_flaky_tests(ui, report, shard_queue)
            wait_for_results(ui, report, shard_queue)
        finally:
            shard_queue.terminate()
            shard_queue.join()

        get_and_attach_logs_for_failing_tests(fleet, report, self.printer)

        return report
