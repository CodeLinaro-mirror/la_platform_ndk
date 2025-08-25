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

import multiprocessing
import os
import subprocess
from pathlib import Path
from subprocess import CompletedProcess

from ndk.abis import Abi
from ndk.ext.subprocess import async_run


def make_build_command(ndk_path: Path) -> list[str]:
    ndk_build_path = ndk_path / "ndk-build"
    cmd = [str(ndk_build_path)]
    if os.name == "nt":
        cmd = ["cmd", "/c"] + cmd
    return cmd


async def build(
    ndk_path: Path,
    project_path: Path,
    abis: list[Abi] | None = None,
    min_sdk_version: int | None = None,
    jobs: int = multiprocessing.cpu_count(),
    dist_dir: Path | None = None,
    flags: list[str] | None = None,
) -> CompletedProcess[bytes]:
    """Invokes ndk-build with the given arguments."""
    args = make_build_command(ndk_path)
    if jobs != 1:
        args.extend([f"-j{jobs}", f"-l{jobs}"])
    if abis is not None:
        args.append(f"APP_ABI={','.join(abis)}")
    if min_sdk_version is not None:
        args.append(f"APP_PLATFORM=android-{min_sdk_version}")
    if dist_dir is not None:
        args.append(f"NDK_LIBS_OUT={dist_dir}")

    if flags is not None:
        args.extend(flags)

    return await async_run(
        args,
        check=False,
        cwd=project_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
