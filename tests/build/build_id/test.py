#
# Copyright (C) 2020 The Android Open Source Project
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
"""Check that --build-id is set appropriately for each linker.

https://github.com/android/ndk/issues/885

We need to use --build-id=sha1 with LLD until there's a new LLDB available in
Studio.
"""
from pathlib import Path
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Checks correct --build-id use."""
    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    verifier.expect_flag("-Wl,--build-id=sha1")
    verifier.expect_not_flag("-Wl,--build-id")
    return verifier.verify().make_test_result_tuple()
