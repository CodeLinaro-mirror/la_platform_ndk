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
from pathlib import Path

import pytest

import ndk.ext.subprocess
import ndk.paths
from ndk.hosts import Host
from ndk.toolchains import ClangToolchain
from ndkstack import App as NdkStackApp

THIS_DIR = Path(__file__).parent.resolve()
INPUTS_DIR = THIS_DIR / "files"


TEST_CONFIGS: list[tuple[str, str, Path]] = [
    ("backtrace.txt", "expected.txt", INPUTS_DIR),
    ("multiple.txt", "expected_multiple.txt", INPUTS_DIR),
    ("hwasan.txt", "expected_hwasan.txt", INPUTS_DIR),
    ("invalid_unicode_log.txt", "expected_invalid_unicode_log.txt", INPUTS_DIR),
    (
        "zipped_symbols_log.txt",
        "zipped_symbols_expected.txt",
        INPUTS_DIR / "native-debug-symbols.zip",
    ),
]


@pytest.mark.parametrize("trace_file,golden_file,symbol_source_path", TEST_CONFIGS)
def test_golden_files(
    trace_file: str,
    golden_file: str,
    symbol_source_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Tests that the sample input traces produce the expected outputs.

    These tests are the same as test_with_built_ndk, but because they test via import of
    ndkstack rather than by shelling out to the built ndk-stack, they're much quicker
    and failure messages will be less cluttered.
    """
    trace_path = INPUTS_DIR / trace_file
    with trace_path.open("rb") as input_file:
        NdkStackApp(
            input_file,
            symbol_source_path,
            llvm_tools_bin=ClangToolchain.path_for_host(Host.current()) / "bin",
        ).run()
    captured = capsys.readouterr()

    expected = (INPUTS_DIR / golden_file).read_text()
    expected = expected.replace("SYMBOL_DIR", str(symbol_source_path))
    assert captured.out == expected


@pytest.mark.requires_ndk
@pytest.mark.parametrize("trace_file,golden_file,symbol_source_path", TEST_CONFIGS)
def test_with_built_ndk(
    trace_file: str, golden_file: str, symbol_source_path: Path
) -> None:
    """Runs the same tests as test_golden_files via the final ndk-stack binary.

    This test catches any issues with the packaging of ndk-stack itself. When avoiding
    the cost of an ndk-stack rebuild during development (that is, editing the Python
    source and running the tests without an intermediate ./checkbuild.py), this test
    will likely fail even if the other test passes because the two are out of sync. When
    developing in this manner, the test can be skipped to avoid the clutter from test
    failures by passing `-m "not requires_ndk"` to pytest. Be sure to build and run
    without that flag before submitting though.
    """
    ndk_path = ndk.paths.get_install_path()
    if not ndk_path.exists():
        pytest.fail(f"{ndk_path} does not exist")

    ndk_stack = ndk_path / "ndk-stack"
    if Host.current() is Host.Windows64:
        ndk_stack = ndk_stack.with_suffix(".bat")

    proc = subprocess.run(
        [
            ndk_stack,
            "-s",
            str(symbol_source_path),
            "-i",
            os.path.join(INPUTS_DIR, trace_file),
        ],
        check=True,
        capture_output=True,
    )

    expected = (INPUTS_DIR / golden_file).read_bytes()
    expected = expected.replace(b"SYMBOL_DIR", str(symbol_source_path).encode("utf-8"))
    assert expected == proc.stdout
