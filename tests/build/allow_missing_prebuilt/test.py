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
"""Check that LOCAL_ALLOW_MISSING_PREBUILT is obeyed."""
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

from ndk.test.spec import BuildConfiguration


PROJECT_PATH = Path("project")


def ndk_build(
    ndk_path: str, config: BuildConfiguration, sync_only: bool = False
) -> tuple[bool, str]:
    ndk_build_path = os.path.join(ndk_path, "ndk-build")
    if sys.platform == "win32":
        ndk_build_path += ".cmd"
    ndk_args = [
        f"APP_ABI={config.abi}",
        f"APP_PLATFORM=android-{config.api}",
    ]
    if sync_only:
        ndk_args.append("-n")
    proc = subprocess.run(
        [ndk_build_path, "-C", str(PROJECT_PATH)] + ndk_args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    return proc.returncode == 0, proc.stdout


def check_build_fail_if_missing(
    ndk_path: str, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    success, output = ndk_build(ndk_path, config)
    if not success:
        return None
    return f"Build should have failed because prebuilts are missing:\n{output}"


def check_sync_pass_if_missing(
    ndk_path: str, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    success, output = ndk_build(ndk_path, config, sync_only=True)
    if success:
        return None
    return f"Build should have passed because ran with -n:\n{output}"


def check_build_pass_if_present(
    ndk_path: str, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    prebuilt_dir = PROJECT_PATH / "jni" / config.abi
    prebuilt_dir.mkdir(parents=True)
    (prebuilt_dir / "libfoo.a").touch()
    (prebuilt_dir / "libfoo.so").touch()
    success, output = ndk_build(ndk_path, config)
    if success:
        return None
    return f"Build should have passed because prebuilts are present:\n{output}"


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, str]:
    """Check that LOCAL_ALLOW_MISSING_PREBUILT is obeyed.

    LOCAL_ALLOW_MISSING_PREBUILT should prevent
    PREBUILT_SHARED_LIBRARY/PREBUILT_STATIC_LIBRARY modules from failing-fast
    when the prebuilt is not present. This is sometimes used for AGP projects
    where the "pre" built is actually built by another module but AGP still
    needs to sync the gradle project before anything is built. The *build* will
    still fail if the library doesn't exist by the time it is needed, but
    that's caused by the failing copy rule.
    """
    if (error := check_build_fail_if_missing(ndk_path, config)) is not None:
        return False, error
    if (error := check_sync_pass_if_missing(ndk_path, config)) is not None:
        return False, error
    if (error := check_build_pass_if_present(ndk_path, config)) is not None:
        return False, error
    return True, ""
