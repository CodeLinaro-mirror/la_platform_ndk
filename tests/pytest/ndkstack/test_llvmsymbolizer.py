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
from dataclasses import dataclass
from pathlib import Path

import pytest

import ndk.paths
import ndkstack
from ndk.hosts import Host

THIS_DIR = Path(__file__).parent
TEST_FILES = THIS_DIR / "files"


@dataclass(frozen=True)
class NdkContext:
    ndk_root: Path
    ndk_bin: Path
    host_tag: str


@pytest.fixture(name="ndk_context")
def ndk_context_fixture() -> NdkContext | None:
    root = ndk.paths.get_install_path()
    if not root.exists():
        return None
    host_tag = Host.current().tag
    return NdkContext(
        root, root / "toolchains/llvm/prebuilt" / host_tag / "bin", host_tag
    )


def test_symbolize(ndk_context: NdkContext | None) -> None:
    if ndk_context is None:
        pytest.skip("could not find NDK")

    with ndkstack.LlvmSymbolizer.launch(
        ndk_context.ndk_root, ndk_context.ndk_bin, ndk_context.host_tag
    ) as symbolizer:
        assert list(symbolizer.symbolize(TEST_FILES / "libc.so", b"0002a019")) == [
            b"pthread_atfork",
            b"bionic/libc/arch-common/bionic/pthread_atfork.h:33:10",
        ]
