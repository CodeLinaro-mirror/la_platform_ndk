# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Runs the tests built by make_tests.py."""
from __future__ import absolute_import, print_function

import argparse
import logging
import sys
from asyncio import CancelledError
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional

from rich.logging import RichHandler

import ndk.notify
import ndk.paths
import ndk.test.builder
from ndk.pythonenv import ensure_python_environment
from ndk.test.filters import TestFilter
from ndk.test.printers import StdoutPrinter
from ndk.test.result import ResultTranslations
from ndk.test.spec import BuildConfiguration, TestSpec
from ndk.timer import Timer, TimingReport

from .case import TestCase
from .testplan import TestPlan
from .testrunner import TestRunner


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


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


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    doc = "https://android.googlesource.com/platform/ndk/+/mirror-goog-main-ndk/docs/Testing.md"
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

    return parser.parse_args(args)


class Results:
    def __init__(self) -> None:
        self.success: Optional[bool] = None
        self.failure_message: Optional[str] = None
        self.timing_report = TimingReport()

    def passed(self) -> None:
        if self.success is not None:
            raise ValueError
        self.success = True

    def failed(self, message: Optional[str] = None) -> None:
        if self.success is not None:
            raise ValueError
        self.success = False
        self.failure_message = message

    @contextmanager
    def timed(self, description: str) -> Iterator[None]:
        with self.timing_report.timed(description):
            yield


async def rebuild_tests(
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
        report = await builder.build()

    if report.num_tests == 0:
        results.failed("Found no tests for filter {}.".format(args.filter))
        return False

    build_printer.print_summary(report)
    if not report.successful:
        results.failed()
        return False

    return True


async def run_tests(args: argparse.Namespace) -> Results:
    results = Results()

    if not args.test_dir.exists():
        if args.rebuild:
            args.test_dir.mkdir(parents=True)
        else:
            sys.exit("Test output directory does not exist: {}".format(args.test_dir))

    if args.package and not args.dist_dir.exists():
        if args.rebuild:
            args.dist_dir.mkdir(parents=True)

    test_spec = TestSpec.load(args.config, abis=args.abi)

    printer = StdoutPrinter(show_all=args.show_all)

    test_dist_dir = args.test_dir / "dist"
    if args.rebuild:
        if not await rebuild_tests(args, results, test_spec):
            return results

    test_filter = TestFilter.from_string(args.filter)
    runner = TestRunner(
        test_spec, test_filter, printer, timing_report=results.timing_report
    )
    runner.add_tests(test_dist_dir, args.test_src)

    if not runner.has_tests():
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
        print_test_stats(runner.test_plan)

    try:
        if (
            error := await runner.run(args.clean_device, args.require_all_devices)
        ) is not None:
            results.failed(error)
        else:
            results.passed()
    except CancelledError:
        results.failed("Test run canceled")
    return results


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    ensure_python_environment()

    log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    verbosity = min(args.verbose, len(log_levels) - 1)
    log_level = log_levels[verbosity]
    logging.basicConfig(level=log_level, handlers=[RichHandler(level=log_level)])

    total_timer = Timer()
    with total_timer:
        results = await run_tests(args)

    if results.success is None:
        raise RuntimeError("run_tests returned without indicating success or failure.")

    good = results.success
    print("Finished {}".format("successfully" if good else "unsuccessfully"))
    if (message := results.failure_message) is not None:
        print(message)

    for timer, duration in results.timing_report.times.items():
        print("{}: {}".format(timer, duration))
    print("Total: {}".format(total_timer.duration))

    subject = "NDK Testing {}!".format("Passed" if good else "Failed")
    body = "Testing finished in {}".format(total_timer.duration)
    ndk.notify.toast(subject, body)

    sys.exit(not good)
