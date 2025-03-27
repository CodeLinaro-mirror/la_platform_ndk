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
"""Check for branch protection flag support for arm64-v8a."""
from pathlib import Path
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.flag_verifier import FlagVerifier


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, Optional[str]]:
    """Checks LOCAL_BRANCH_PROTECTION is propagated for arm64-v8a."""
    verifier = FlagVerifier(Path("project"), Path(ndk_path), config)
    if config.abi == "arm64-v8a":
        verifier.expect_flag("-mbranch-protection=standard")
    else:
        verifier.expect_not_flag("-mbranch-protection=standard")
    return verifier.verify_ndk_build().make_test_result_tuple()
