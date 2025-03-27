#
# Copyright (C) 2023 The Android Open Source Project
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

from .ndkversionheadergenerator import NdkVersionHeaderGenerator


def test_ndkversionheadergenerator_generate_str() -> None:
    text = NdkVersionHeaderGenerator(
        major=26, minor=0, beta=0, build_number=1234, canary=False
    ).generate_str()
    lines = text.splitlines()
    assert "#define __NDK_MAJOR__ 26" in lines
    assert "#define __NDK_MINOR__ 0" in lines
    assert "#define __NDK_BETA__ 0" in lines
    assert "#define __NDK_BUILD__ 1234" in lines
    assert "#define __NDK_CANARY__ 0" in lines

    text = NdkVersionHeaderGenerator(
        major=27, minor=1, beta=2, build_number=0, canary=True
    ).generate_str()
    lines = text.splitlines()
    assert "#define __NDK_MAJOR__ 27" in lines
    assert "#define __NDK_MINOR__ 1" in lines
    assert "#define __NDK_BETA__ 2" in lines
    assert "#define __NDK_BUILD__ 0" in lines
    assert "#define __NDK_CANARY__ 1" in lines


def test_ndkversionheader_write(tmp_path: Path) -> None:
    generator = NdkVersionHeaderGenerator(
        major=26, minor=0, beta=0, build_number=1234, canary=False
    )
    text = generator.generate_str()
    output = tmp_path / "ndk-version.h"
    generator.write(output)
    assert text == output.read_text()
