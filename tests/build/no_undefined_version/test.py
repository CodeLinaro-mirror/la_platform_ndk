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
"""Check that -Wl,--no-undefined-version is used.

Without this flag, LLD will not verify that the public symbols in a version script are
present in the library.
"""
from pathlib import Path
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Checks correct --no-undefined-version use."""
    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.expect_flag("-Wl,--no-undefined-version")
    result = verifier.verify()
    if result.failed():
        return result.make_test_result_tuple()

    # LOCAL_* flags shouldn't normally be specified on the command-line, but per module
    # in the Android.mk. It's unusual, but doing it this way lets us avoid duplicating
    # the test.
    verifier = (
        FlagVerifier(Path("project"), Path(ndk_path), config)
        .with_cmake_flag("-DANDROID_ALLOW_UNDEFINED_VERSION_SCRIPT_SYMBOLS=ON")
        .with_ndk_build_flag("LOCAL_ALLOW_UNDEFINED_VERSION_SCRIPT_SYMBOLS=true")
    )
    verifier.expect_not_flag("-Wl,--no-undefined-version")
    return verifier.verify().make_test_result_tuple()
