#
# Copyright (C) 2022 The Android Open Source Project
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
"""Check that -Wl,--gc-sections is used, but only on release builds.

This flag should not be present for debug builds because that can strip functions that
the user may want to evaluate while debugging.

https://github.com/android/ndk/issues/1717
https://github.com/android/ndk/issues/1813
"""
from pathlib import Path
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Checks correct --gc-sections use."""
    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.with_cmake_flag("-DCMAKE_BUILD_TYPE=Release")
    verifier.with_ndk_build_flag("APP_DEBUG=false")
    verifier.expect_flag("-Wl,--gc-sections")
    passed, message = verifier.verify().make_test_result_tuple(
        "With -DCMAKE_BUILD_TYPE=Release and APP_DEBUG=false"
    )
    if not passed:
        return passed, message

    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.with_cmake_flag("-DCMAKE_BUILD_TYPE=RelWithDebInfo")
    verifier.expect_flag("-Wl,--gc-sections")
    passed, message = verifier.verify_cmake().make_test_result_tuple(
        "With -DCMAKE_BUILD_TYPE=RelWithDebInfo"
    )
    if not passed:
        return passed, message

    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.with_cmake_flag("-DCMAKE_BUILD_TYPE=MinSizeRel")
    verifier.expect_flag("-Wl,--gc-sections")
    passed, message = verifier.verify_cmake().make_test_result_tuple(
        "With -DCMAKE_BUILD_TYPE=MinSizeRel"
    )
    if not passed:
        return passed, message

    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.with_cmake_flag("-DCMAKE_BUILD_TYPE=Debug")
    verifier.with_ndk_build_flag("APP_DEBUG=true")
    verifier.expect_not_flag("-Wl,--gc-sections")
    return verifier.verify().make_test_result_tuple(
        "With -DCMAKE_BUILD_TYPE=Debug and APP_DEBUG=true"
    )
