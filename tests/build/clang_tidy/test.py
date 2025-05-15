#
# Copyright (C) 2018 The Android Open Source Project
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
"""Test that we get warnings from clang-tidy."""
from subprocess import CalledProcessError
from pathlib import Path

from ndk.test.spec import BuildConfiguration
from ndk.testing.builders import NdkBuildBuilder


def run_test(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> tuple[bool, str]:
    """Checks ndk-build V=1 output for clang-tidy warnings."""
    builder = NdkBuildBuilder.from_build_config(test_dir / "project", ndk_path, config)
    try:
        out = builder.build()
    except CalledProcessError as ex:
        return False, ex.stdout

    expect = "warning: parameter 'argc' is unused [misc-unused-parameters]"
    return expect in out, out
