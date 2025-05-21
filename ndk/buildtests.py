# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Builds and packages the NDK's tests.

This is typically done by checkbuild.py or by run_tests.py when `--rebuild` is used, but
the Windows NDK is cross compiled from Linux, which means the test build for that target
has to be done by a separate build on a Windows machine. This tool provides an entry
point for that separate from `run_tests.py --build-only` to allow the test runner code,
which only ever runs in a local development environment, to avoid needing to be cautious
about how it imports package from PyPI, which aren't available in CI.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import multiprocessing
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

import ndk.archive
import ndk.paths
from ndk.test.builder import TestBuilder
from ndk.test.printers import StdoutPrinter
from ndk.test.spec import TestOptions

try:
    from rich.logging import RichHandler

    CAN_USE_RICH = True
except ModuleNotFoundError:
    CAN_USE_RICH = False


class App:
    def __init__(
        self,
        ndk_path: Path,
        out_dir: Path,
        dist_dir: Path,
        clean: bool,
        package: bool,
    ) -> None:
        self.ndk_path = ndk_path
        self.out_dir = out_dir
        self.dist_dir = dist_dir
        self.clean = clean
        self.package = package

    @staticmethod
    def main(argv: Sequence[str] | None = None) -> None:
        asyncio.run(App.from_args(argv).run())

    @staticmethod
    def from_args(argv: Sequence[str] | None = None) -> App:
        parser = argparse.ArgumentParser()

        build_options = parser.add_argument_group("Build Options")
        build_options.add_argument(
            "--clean",
            action="store_true",
            help="Remove the out directory before building.",
        )
        build_options.add_argument(
            "--package",
            action="store_true",
            help="Package the built tests.",
        )

        parser.add_argument(
            "--ndk",
            type=Path,
            default=ndk.paths.get_install_path(),
            help="NDK to validate. Defaults to ../out/android-ndk-$RELEASE.",
        )

        parser.add_argument(
            "--out-dir",
            type=Path,
            default=ndk.paths.get_out_dir(),
            help="Directory for storing intermediate build outputs.",
        )

        parser.add_argument(
            "--dist-dir",
            type=Path,
            default=ndk.paths.get_dist_dir(),
            help="Directory to store packaged tests. Defaults to $DIST_DIR or ../out/dist",
        )

        args = parser.parse_args(argv)
        return App(args.ndk, args.out_dir, args.dist_dir, args.clean, args.package)

    async def run(self) -> None:
        log_level = logging.INFO
        handlers = None
        if CAN_USE_RICH:
            handlers = [RichHandler(level=log_level)]
        logging.basicConfig(level=log_level, handlers=handlers)

        logging.info("Machine has %d CPUs", multiprocessing.cpu_count())
        error = await self.build_tests()
        if error is not None:
            sys.exit(error)

    async def build_tests(self) -> str | None:
        test_src_dir = ndk.paths.ndk_path("tests")
        test_out_dir = self.out_dir / "tests"

        if not self.ndk_path.exists():
            sys.exit(f"{self.ndk_path} does not exist")

        extracted_ndk_path = self.ndk_path
        if self.ndk_path.is_file():
            # Extract to a known location rather than a directory named matching
            # the release for ease of use, and use a short name to avoid path
            # length issues on the Windows bots.
            extracted_ndk_path = self.out_dir / "ndk-zip"
            logging.info("Extracting %s to %s", self.ndk_path, extracted_ndk_path)
            self.extract_ndk(extracted_ndk_path)

        test_options = TestOptions(
            test_src_dir,
            extracted_ndk_path,
            test_out_dir,
            clean=self.clean,
            package_path=(self.dist_dir / "ndk-tests" if self.package else None),
        )

        printer = StdoutPrinter()

        test_spec = ndk.test.spec.TestSpec.load(ndk.paths.ndk_path("qa_config.json"))
        builder = TestBuilder(test_spec, test_options, printer)

        report = await builder.build()
        printer.print_summary(report)

        if not report.num_tests:
            return "No tests were built"

        if not report.successful:
            # Write out the result to logs/build_error.log so we can find the
            # failure easily on the build server.
            log_path = self.dist_dir / "logs" / "build_error.log"
            with log_path.open("a", encoding="utf-8") as error_log:
                error_log_printer = ndk.test.printers.FilePrinter(error_log)
                error_log_printer.print_summary(report)
            return "Test build failed"

        return None

    def extract_ndk(self, dest: Path) -> None:
        # Extracting to a temp dir in the out directory rather than using tempdir
        # because the system's temp dir might be on another volume, and we want to be
        # able to move without copying.
        temp_dir = self.out_dir / "temp-extract-ndk"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True)
        try:
            ndk.archive.unzip(self.ndk_path, temp_dir)
            contents = list(temp_dir.iterdir())
            assert len(contents) == 1
            assert contents[0].is_dir()
            if dest.exists():
                shutil.rmtree(dest)
            contents[0].rename(dest)
        finally:
            shutil.rmtree(temp_dir)
