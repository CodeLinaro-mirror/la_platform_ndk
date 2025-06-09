#
# Copyright (C) 2021 The Android Open Source Project
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
"""Check that the CMake toolchain uses the correct default flags."""
from pathlib import Path
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier, FlagVerifierResult


def check_configuration(
    ndk_path: str,
    build_config: BuildConfiguration,
    cmake_config: str,
    expected_flags: list[str],
    unexpected_flags: list[str],
) -> FlagVerifierResult:
    verifier = FlagVerifier(
        Path("project"), Path(ndk_path), build_config
    ).with_cmake_flag(f"-DCMAKE_BUILD_TYPE={cmake_config}")
    for flag in expected_flags:
        verifier.expect_flag(flag)
    for flag in unexpected_flags:
        verifier.expect_not_flag(flag)
    return verifier.verify_cmake()


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Check that the CMake toolchain uses the correct default flags."""
    verify_configs: dict[str, tuple[list[str], list[str]]] = {
        # No flag is the same as -O0. As long as no other opt flag is used, the default
        # is fine.
        "Debug": ([], ["-O1", "-O2", "-O3", "-Os", "-Oz"]),
        "MinSizeRel": (["-Os"], ["-O0", "-O1", "-O2", "-O3", "-Oz"]),
        "Release": (["-O3"], ["-O0", "-O1", "-O2", "-Os", "-Oz"]),
        "RelWithDebInfo": (["-O2"], ["-O0", "-O1", "-O3", "-Os", "-Oz"]),
    }
    for cmake_config, (expected_flags, unexpected_flags) in verify_configs.items():
        result = check_configuration(
            ndk_path, config, cmake_config, expected_flags, unexpected_flags
        )
        if result.failed():
            return result.make_test_result_tuple()
    return result.make_test_result_tuple()
