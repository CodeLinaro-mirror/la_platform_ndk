#
# Copyright (C) 2025 The Android Open Source Project
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
from pathlib import Path

import pytest

import ndkstack
from ndk.hosts import Host
from ndk.toolchains import ClangToolchain

THIS_DIR = Path(__file__).parent
TEST_FILES = THIS_DIR / "files"


@pytest.fixture(name="llvm_tools_bin")
def llvm_tools_bin_fixture() -> Path:
    return ClangToolchain.path_for_host(Host.current()) / "bin"


def test_symbolize(llvm_tools_bin: Path) -> None:
    with ndkstack.LlvmSymbolizer.launch(llvm_tools_bin) as symbolizer:
        assert list(symbolizer.symbolize(TEST_FILES / "libc.so", b"0002a019")) == [
            b"pthread_atfork",
            b"bionic/libc/arch-common/bionic/pthread_atfork.h:33:10",
        ]
