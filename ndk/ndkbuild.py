#
# Copyright (C) 2015 The Android Open Source Project
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
"""APIs for interacting with ndk-build."""
from __future__ import absolute_import

import os
import subprocess
from pathlib import Path
from subprocess import CompletedProcess


def make_build_command(ndk_path: Path, build_flags: list[str]) -> list[str]:
    ndk_build_path = ndk_path / "ndk-build"
    cmd = [str(ndk_build_path)] + build_flags
    if os.name == "nt":
        cmd = ["cmd", "/c"] + cmd
    return cmd


def build(ndk_path: Path, build_flags: list[str]) -> CompletedProcess[str]:
    """Invokes ndk-build with the given arguments."""
    return subprocess.run(
        make_build_command(ndk_path, build_flags),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
