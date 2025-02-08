#!/usr/bin/env python3
#
# Copyright (C) 2019 The Android Open Source Project
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
"""System tests for ndk-stack.py"""

import os.path
import subprocess
import unittest
from pathlib import Path

import ndk.ext.subprocess
import ndk.paths
import ndk.toolchains
from ndk.hosts import Host

THIS_DIR = Path(__file__).parent.resolve()
INPUTS_DIR = THIS_DIR / "files"


class SystemTests(unittest.TestCase):
    """Complete system test of ndk-stack.py script."""

    def setUp(self) -> None:
        self.maxDiff = None

        ndk_path = ndk.paths.get_install_path()
        self.assertTrue(
            ndk_path.exists(),
            f"{ndk_path} does not exist. Build the NDK before running this test.",
        )

        ndk_stack = ndk_path / "ndk-stack"
        if Host.current() is Host.Windows64:
            ndk_stack = ndk_stack.with_suffix(".bat")
        self.ndk_stack = ndk_stack

    def system_test(
        self, backtrace_file: str, expected_file: str, symbol_dir: Path | None = None
    ) -> None:
        if symbol_dir is None:
            symbol_dir = INPUTS_DIR

        proc = subprocess.run(
            [
                self.ndk_stack,
                "-s",
                str(symbol_dir),
                "-i",
                os.path.join(INPUTS_DIR, backtrace_file),
            ],
            check=True,
            capture_output=True,
        )

        # Read the expected output.
        file_name = os.path.join(INPUTS_DIR, expected_file)
        with open(file_name, "rb") as exp_file:
            expected = exp_file.read()
        expected = expected.replace(b"SYMBOL_DIR", str(symbol_dir).encode("utf-8"))
        self.assertEqual(expected.decode("utf-8"), proc.stdout.decode("utf-8"))

    def test_all_stacks(self) -> None:
        self.system_test("backtrace.txt", "expected.txt")

    def test_multiple_crashes(self) -> None:
        self.system_test("multiple.txt", "expected_multiple.txt")

    def test_hwasan(self) -> None:
        self.system_test("hwasan.txt", "expected_hwasan.txt")

    def test_invalid_unicode(self) -> None:
        with ndk.ext.subprocess.verbose_subprocess_errors():
            self.system_test(
                "invalid_unicode_log.txt", "expected_invalid_unicode_log.txt"
            )

    def test_symbols_from_zip(self) -> None:
        """Tests that symbols can be found in native-debug-symbols.zip."""
        with ndk.ext.subprocess.verbose_subprocess_errors():
            self.system_test(
                "zipped_symbols_log.txt",
                "zipped_symbols_expected.txt",
                symbol_dir=INPUTS_DIR / "native-debug-symbols.zip",
            )


if __name__ == "__main__":
    unittest.main()
