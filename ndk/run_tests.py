#!/usr/bin/env python3
#
# Copyright (C) 2017 The Android Open Source Project
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
"""Runs the tests built by make_tests.py."""
from __future__ import absolute_import, print_function

import argparse
import collections
import datetime
import logging
import random
import shutil
import site
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional

import ndk.ansi
import ndk.archive
import ndk.ext.subprocess
import ndk.notify
import ndk.paths
import ndk.test.builder
import ndk.test.buildtest.case
import ndk.test.ui
import ndk.ui
from ndk.test.devices import (
    Device,
    DeviceConfig,
    DeviceFleet,
    DeviceShardingGroup,
    find_devices,
)
from ndk.test.devicetest.case import TestCase
from ndk.test.devicetest.testgroup import TestGroup
from ndk.test.devicetest.testplan import TestPlan
from ndk.test.devicetest.testrun import TestRun
from ndk.test.filters import TestFilter
from ndk.test.printers import Printer, StdoutPrinter
from ndk.test.report import Report
from ndk.test.result import (
    Failure,
    ResultTranslations,
    Skipped,
    TestResult,
    UnexpectedSuccess,
)
from ndk.test.spec import BuildConfiguration, TestSpec
from ndk.timer import Timer
from ndk.workqueue import ShardingWorkQueue, Worker, WorkQueue

from .pythonenv import ensure_python_environment


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def clear_test_directory(_worker: Worker, device: Device) -> None:
    print(f"Clearing test directory on {device}")
    cmd = ["rm", "-r", str(ndk.paths.DEVICE_TEST_BASE_DIR)]
    logger().info('%s: shell_nocheck "%s"', device.name, cmd)
    device.shell_nocheck(cmd)


def clear_test_directories(workqueue: WorkQueue, fleet: DeviceFleet) -> None:
    for group in fleet.get_unique_device_groups():
        for device in group.devices:
            workqueue.add_task(clear_test_directory, device)

    while not workqueue.finished():
        workqueue.get_result()


def adb_has_feature(feature: str) -> bool:
    cmd = ["adb", "host-features"]
    logger().info('check_output "%s"', " ".join(cmd))
    output = subprocess.check_output(cmd).decode("utf-8")
    features_line = output.splitlines()[-1]
    features = features_line.split(",")
    return feature in features


def push_tests_to_device(
    worker: Worker,
    test_group: TestGroup,
    dest_dir: PurePosixPath,
    device: Device,
    use_sync: bool,
) -> None:
    """Pushes a directory to the given device.

    Creates the parent directory on the device if needed.

    Args:
        worker: The worker performing the task.
        test_group: The group of tests to push.
        dest_dir: The destination directory on the device. Note that when
                  pushing a directory, dest_dir will be the parent directory,
                  not the destination path.
        device: The device to push to.
        use_sync: True if `adb push --sync` is supported.
    """
    worker.status = f"Pushing {test_group.build_config} tests to {device}."
    logger().info("%s: mkdir %s", device.name, dest_dir)
    device.shell_nocheck(["mkdir", str(dest_dir)])
    logger().info(
        "%s: push%s %s %s",
        device.name,
        " --sync" if use_sync else "",
        test_group.host_path,
        dest_dir,
    )
    device.push(str(test_group.host_path), str(dest_dir), sync=use_sync)
    # Tests that were built and bundled on Windows but pushed from Linux or macOS will
    # not have execute permission by default. Since we don't know where the tests came
    # from, chmod all the tests regardless.
    device.shell(["chmod", "-R", "777", str(dest_dir)])


def push_tests_to_devices(
    workqueue: WorkQueue,
    test_plan: TestPlan,
    fleet: DeviceFleet,
    use_sync: bool,
) -> None:
    dest_dir = ndk.paths.DEVICE_TEST_BASE_DIR
    for test_group in test_plan.iter_test_groups():
        for group in fleet.get_unique_device_groups():
            if group.can_run_build_config(test_group.build_config):
                for device in group.devices:
                    workqueue.add_task(
                        push_tests_to_device,
                        test_group,
                        dest_dir,
                        device,
                        use_sync,
                    )

    ndk.ui.finish_workqueue_with_ui(workqueue, ndk.ui.get_work_queue_ui)
    print("Finished pushing tests")


def run_test(worker: Worker, test: TestRun) -> TestResult:
    device = worker.data[0]
    worker.status = f"Running {test.name}"
    return test.run(device)


def print_test_stats(test_plan: TestPlan) -> None:
    test_stats: Dict[BuildConfiguration, Dict[str, List[TestCase]]] = {}
    for test_group in test_plan.iter_test_groups():
        test_stats[test_group.build_config] = {}
        for test in test_group.tests:
            if test.build_system not in test_stats[test_group.build_config]:
                test_stats[test_group.build_config][test.build_system] = []
            test_stats[test_group.build_config][test.build_system].append(test)

    for config, build_system_groups in test_stats.items():
        print(f"Config {config}:")
        for build_system, tests in build_system_groups.items():
            print(f"\t{build_system}: {len(tests)} tests")


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


def pair_test_runs(
    test_plan: TestPlan, report: Report[DeviceShardingGroup], fleet: DeviceFleet
) -> List[TestRun]:
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


def report_skipped_tests_for_missing_devices(
    report: Report[DeviceShardingGroup], test_group: TestGroup, fleet: DeviceFleet
) -> None:
    for group in fleet.get_missing():
        device_config = DeviceConfig(group.abis, group.version, group.supports_mte)
        if not device_config.can_run_build_config(test_group.build_config):
            # These are a configuration that will never be valid, like a minSdkVersion
            # 30 test on an API 21 device. No need to report these.
            continue
        for test_case in test_group.tests:
            report.add_result(
                test_case.build_system,
                Skipped(TestRun(test_case, group), "No devices available"),
            )


def wait_for_results(
    report: Report[DeviceShardingGroup],
    workqueue: ShardingWorkQueue[TestResult, Device],
    printer: Printer,
) -> None:
    console = ndk.ansi.get_console()
    ui = ndk.test.ui.get_test_progress_ui(console, workqueue)
    with ndk.ansi.disable_terminal_echo(sys.stdin):
        with console.cursor_hide_context():
            while not workqueue.finished():
                results = workqueue.get_results()
                verbose = logger().isEnabledFor(logging.INFO)
                if verbose or any(r.failed() for r in results):
                    ui.clear()
                for result in results:
                    suite = result.test.build_system
                    report.add_result(suite, result)
                    if verbose or result.failed():
                        printer.print_result(result)
                ui.draw()
            ui.clear()


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
    report: Report[DeviceShardingGroup],
    workqueue: ShardingWorkQueue[TestResult, Device],
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


def run_and_collect_logs(worker: Worker, test_run: TestRun) -> TestResult:
    device: Device = worker.data[0]
    worker.status = "Clearing device log"
    device.clear_logcat()
    result = run_test(worker, test_run)
    if not isinstance(result, Failure):
        logger().warning(
            "Failing test passed on re-run while collecting logs. This makes testing "
            "slower. Test flake should be investigated."
        )
        return result
    worker.status = "Collecting device log"
    log = device.logcat()
    result.message += f"\nlogcat contents:\n{log}"
    return result


def get_and_attach_logs_for_failing_tests(
    fleet: DeviceFleet, report: Report[DeviceShardingGroup], printer: Printer
) -> None:
    failures = report.remove_all_true_failures()
    if not failures:
        return

    # Have to use max of one worker per re-run to ensure that the logs we collect do not
    # conflate with other tests.
    queue: ShardingWorkQueue[TestResult, Device] = ShardingWorkQueue(
        fleet.get_unique_device_groups(), 1
    )
    try:
        for failure in failures:
            queue.add_task(failure.user_data, run_and_collect_logs, failure.test)
        wait_for_results(report, queue, printer)
    finally:
        queue.terminate()
        queue.join()


def str_to_bool(s: str) -> bool:
    if s == "true":
        return True
    if s == "false":
        return False
    raise ValueError(s)


def parse_args() -> argparse.Namespace:
    doc = "https://android.googlesource.com/platform/ndk/+/master/docs/Testing.md"
    parser = argparse.ArgumentParser(epilog="See {} for more information.".format(doc))

    def PathArg(path: str) -> Path:
        # Path.resolve() fails if the path doesn't exist. We want to resolve
        # symlinks when possible, but not require that the path necessarily
        # exist, because we will create it later.
        return Path(path).expanduser().resolve(strict=False)

    def ExistingPathArg(path: str) -> Path:
        expanded_path = Path(path).expanduser()
        if not expanded_path.exists():
            raise argparse.ArgumentTypeError("{} does not exist".format(path))
        return expanded_path.resolve(strict=True)

    def ExistingDirectoryArg(path: str) -> Path:
        expanded_path = Path(path).expanduser()
        if not expanded_path.is_dir():
            raise argparse.ArgumentTypeError("{} is not a directory".format(path))
        return expanded_path.resolve(strict=True)

    def ExistingFileArg(path: str) -> Path:
        expanded_path = Path(path).expanduser()
        if not expanded_path.is_file():
            raise argparse.ArgumentTypeError("{} is not a file".format(path))
        return expanded_path.resolve(strict=True)

    config_options = parser.add_argument_group("Test Configuration Options")
    config_options.add_argument(
        "--filter", help="Only run tests that match the given pattern."
    )
    config_options.add_argument(
        "--abi",
        action="append",
        choices=ndk.abis.ALL_ABIS,
        help="Test only the given APIs.",
    )

    # The type ignore is needed because realpath is an overloaded function, and
    # mypy is bad at those (it doesn't satisfy Callable[[str], AnyStr]).
    config_options.add_argument(
        "--config",
        type=ExistingFileArg,
        default=ndk.paths.ndk_path("qa_config.json"),
        help="Path to the config file describing the test run.",
    )

    build_options = parser.add_argument_group("Build Options")
    build_options.add_argument(
        "--build-report",
        type=PathArg,
        help="Write the build report to the given path.",
    )

    build_exclusive_group = build_options.add_mutually_exclusive_group()
    build_exclusive_group.add_argument(
        "--rebuild", action="store_true", help="Build the tests before running."
    )
    build_exclusive_group.add_argument(
        "--build-only", action="store_true", help="Builds the tests and exits."
    )
    build_options.add_argument(
        "--clean", action="store_true", help="Remove the out directory before building."
    )
    build_options.add_argument(
        "--package",
        action="store_true",
        help="Package the built tests. Requires --rebuild or --build-only.",
    )

    run_options = parser.add_argument_group("Test Run Options")
    run_options.add_argument(
        "--clean-device",
        action="store_true",
        help="Clear the device directories before syncing.",
    )
    run_options.add_argument(
        "--require-all-devices",
        action="store_true",
        help="Abort if any devices specified by the config are not available.",
    )

    display_options = parser.add_argument_group("Display Options")
    display_options.add_argument(
        "--show-all",
        action="store_true",
        help="Show all test results, not just failures.",
    )
    display_options.add_argument(
        "--show-test-stats",
        action="store_true",
        help="Print number of tests found for each configuration.",
    )
    display_options.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log level. Defaults to logging.WARNING.",
    )

    parser.add_argument(
        "--ndk",
        type=ExistingPathArg,
        default=ndk.paths.get_install_path(),
        help="NDK to validate. Defaults to ../out/android-ndk-$RELEASE.",
    )
    parser.add_argument(
        "--test-src",
        type=ExistingDirectoryArg,
        default=ndk.paths.ndk_path("tests"),
        help="Path to test source directory. Defaults to ndk/tests.",
    )

    parser.add_argument(
        "test_dir",
        metavar="TEST_DIR",
        type=PathArg,
        nargs="?",
        default=ndk.paths.path_in_out(Path("tests")),
        help="Directory containing built tests.",
    )

    parser.add_argument(
        "--dist-dir",
        type=PathArg,
        default=ndk.paths.get_dist_dir(),
        help="Directory to store packaged tests. Defaults to $DIST_DIR or ../out/dist",
    )

    return parser.parse_args()


class Results:
    def __init__(self) -> None:
        self.success: Optional[bool] = None
        self.failure_message: Optional[str] = None
        self.times: Dict[str, datetime.timedelta] = collections.OrderedDict()

    def passed(self) -> None:
        if self.success is not None:
            raise ValueError
        self.success = True

    def failed(self, message: Optional[str] = None) -> None:
        if self.success is not None:
            raise ValueError
        self.success = False
        self.failure_message = message

    def add_timing_report(self, label: str, timer: Timer) -> None:
        if label in self.times:
            raise ValueError
        assert timer.duration is not None
        self.times[label] = timer.duration

    @contextmanager
    def timed(self, description: str) -> Iterator[None]:
        timer = Timer()
        with timer:
            yield
        self.add_timing_report(description, timer)


def unzip_ndk(ndk_path: Path) -> Path:
    # Unzip the NDK into out/ndk-zip.
    if ndk_path.suffix != ".zip":
        raise ValueError(f"--ndk must be a directory or a .zip file: {ndk}")

    ndk_dir = ndk.paths.path_in_out(Path(ndk_path.stem))
    if ndk_dir.exists():
        shutil.rmtree(ndk_dir)
    ndk_dir.mkdir(parents=True)
    try:
        ndk.archive.unzip(ndk_path, ndk_dir)
        contents = list(ndk_dir.iterdir())
        assert len(contents) == 1
        assert contents[0].is_dir()
        # Windows paths, by default, are limited to 260 characters.
        # Some of our deeply nested paths run up against this limitation.
        # Therefore, after unzipping the NDK into something like
        # out/android-ndk-8136140-windows-x86_64/android-ndk-r25-canary
        # (61 characters) we rename it to out/ndk-zip (7 characters),
        # shortening paths in the NDK by 54 characters.
        short_path = ndk.paths.path_in_out(Path("ndk-zip"))
        if short_path.exists():
            shutil.rmtree(short_path)
        contents[0].rename(short_path)
        return short_path
    finally:
        shutil.rmtree(ndk_dir)


def rebuild_tests(
    args: argparse.Namespace, results: Results, test_spec: TestSpec
) -> bool:
    build_printer = StdoutPrinter(
        show_all=args.show_all,
        result_translations=ResultTranslations(success="BUILT"),
    )
    with results.timed("Build"):
        test_options = ndk.test.spec.TestOptions(
            args.test_src,
            args.ndk,
            args.test_dir,
            test_filter=args.filter,
            clean=args.clean,
            package_path=args.dist_dir / "ndk-tests" if args.package else None,
        )
        builder = ndk.test.builder.TestBuilder(test_spec, test_options, build_printer)
        report = builder.build()

    if report.num_tests == 0:
        results.failed("Found no tests for filter {}.".format(args.filter))
        return False

    build_printer.print_summary(report)
    if not report.successful:
        results.failed()
        return False

    return True


def run_tests(args: argparse.Namespace) -> Results:
    results = Results()

    if not args.test_dir.exists():
        if args.rebuild or args.build_only:
            args.test_dir.mkdir(parents=True)
        else:
            sys.exit("Test output directory does not exist: {}".format(args.test_dir))

    if args.package and not args.dist_dir.exists():
        if args.rebuild or args.build_only:
            args.dist_dir.mkdir(parents=True)

    test_spec = TestSpec.load(args.config, abis=args.abi)

    printer = StdoutPrinter(show_all=args.show_all)

    if args.ndk.is_file():
        args.ndk = unzip_ndk(args.ndk)

    test_dist_dir = args.test_dir / "dist"
    if args.build_only or args.rebuild:
        if not rebuild_tests(args, results, test_spec):
            return results

    if args.build_only:
        results.passed()
        return results

    test_filter = TestFilter.from_string(args.filter)
    test_plan = TestPlan(test_spec, test_filter)
    with results.timed("Test discovery"):
        test_plan.add_tests_from_dist_dir(test_dist_dir, args.test_src)

    if not test_plan.has_tests():
        # As long as we *built* some tests, not having anything to run isn't a
        # failure.
        if args.rebuild:
            results.passed()
        else:
            results.failed(
                "Found no tests in {} for filter {}.".format(test_dist_dir, args.filter)
            )
        return results

    if args.show_test_stats:
        print_test_stats(test_plan)

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
        with results.timed("Device discovery"):
            fleet = find_devices(test_spec.devices, workqueue)

        have_all_devices = verify_have_all_requested_devices(fleet)
        if args.require_all_devices and not have_all_devices:
            results.failed("Some requested devices were not available.")
            return results

        for config in iter_configs_with_no_device(test_plan, fleet):
            logger().warning("No device found for %s.", config)

        if args.clean_device:
            with results.timed("Clean device"):
                clear_test_directories(workqueue, fleet)

        can_use_sync = adb_has_feature("push_sync")
        with results.timed("Push"):
            push_tests_to_devices(workqueue, test_plan, fleet, can_use_sync)
    finally:
        workqueue.terminate()
        workqueue.join()

    report = Report[DeviceShardingGroup]()
    shard_queue: ShardingWorkQueue[TestResult, Device] = ShardingWorkQueue(
        fleet.get_unique_device_groups(), 4
    )
    try:
        # Need an input queue per device group, a single result queue, and a
        # pool of threads per device.

        # Shuffle the test runs to distribute the load more evenly. These are
        # ordered by (build config, device, test), so most of the tests running
        # at any given point in time are all running on the same device.
        test_runs = pair_test_runs(test_plan, report, fleet)
        random.shuffle(test_runs)
        with results.timed("Run"):
            for test_run in test_runs:
                shard_queue.add_task(test_run.device_group, run_test, test_run)

            wait_for_results(report, shard_queue, printer)
            restart_flaky_tests(report, shard_queue)
            wait_for_results(report, shard_queue, printer)
    finally:
        shard_queue.terminate()
        shard_queue.join()

    get_and_attach_logs_for_failing_tests(fleet, report, printer)

    printer.print_summary(report)

    if report.successful:
        results.passed()
    else:
        results.failed()

    return results


def main() -> None:
    args = parse_args()

    ensure_python_environment()

    log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    verbosity = min(args.verbose, len(log_levels) - 1)
    log_level = log_levels[verbosity]
    logging.basicConfig(level=log_level)

    python_packages = args.ndk / "python-packages"
    site.addsitedir(python_packages)

    total_timer = Timer()
    with total_timer:
        results = run_tests(args)

    if results.success is None:
        raise RuntimeError("run_tests returned without indicating success or failure.")

    good = results.success
    print("Finished {}".format("successfully" if good else "unsuccessfully"))
    if (message := results.failure_message) is not None:
        print(message)

    for timer, duration in results.times.items():
        print("{}: {}".format(timer, duration))
    print("Total: {}".format(total_timer.duration))

    subject = "NDK Testing {}!".format("Passed" if good else "Failed")
    body = "Testing finished in {}".format(total_timer.duration)
    ndk.notify.toast(subject, body)

    sys.exit(not good)


if __name__ == "__main__":
    main()
