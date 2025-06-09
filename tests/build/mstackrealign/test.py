#
# Copyright (C) 2016 The Android Open Source Project
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
"""Check for mstackrealign use for old x86 targets.

http://b.android.com/222239 reports that old x86 targets have stack alignment
issues. For these devices, verify that mstackrealign is used.
"""
from pathlib import Path
from typing import Optional

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Checks ndk-build V=1 output for mstackrealign flag."""
    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    assert config.api is not None
    if config.abi == Abi("x86") and config.api < 24:
        verifier.expect_flag("-mstackrealign")
    else:
        verifier.expect_not_flag("-mstackrealign")
    return verifier.verify_ndk_build().make_test_result_tuple()
