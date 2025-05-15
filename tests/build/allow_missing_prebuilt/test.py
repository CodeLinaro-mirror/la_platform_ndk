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
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from ndk.test.spec import BuildConfiguration
from ndk.testing.builders import NdkBuildBuilder


def ndk_build(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration, sync_only: bool = False
) -> tuple[bool, str]:
    flags = []
    if sync_only:
        flags = ["-n"]
    builder = NdkBuildBuilder.from_build_config(
        test_dir / "project", ndk_path, config, flags
    )
    try:
        return True, builder.build()
    except CalledProcessError as ex:
        return False, ex.stdout


def check_build_fail_if_missing(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    success, output = ndk_build(test_dir, ndk_path, config)
    if not success:
        return None
    return f"Build should have failed because prebuilts are missing:\n{output}"


def check_sync_pass_if_missing(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    success, output = ndk_build(test_dir, ndk_path, config, sync_only=True)
    if success:
        return None
    return f"Build should have passed because ran with -n:\n{output}"


def check_build_pass_if_present(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> Optional[str]:
    """Checks that the build fails if the libraries are missing."""
    prebuilt_dir = test_dir / "project/jni" / config.abi
    prebuilt_dir.mkdir(parents=True)
    (prebuilt_dir / "libfoo.a").touch()
    (prebuilt_dir / "libfoo.so").touch()
    success, output = ndk_build(test_dir, ndk_path, config)
    if success:
        return None
    return f"Build should have passed because prebuilts are present:\n{output}"


def run_test(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> tuple[bool, str]:
    """Check that LOCAL_ALLOW_MISSING_PREBUILT is obeyed.

    LOCAL_ALLOW_MISSING_PREBUILT should prevent
    PREBUILT_SHARED_LIBRARY/PREBUILT_STATIC_LIBRARY modules from failing-fast
    when the prebuilt is not present. This is sometimes used for AGP projects
    where the "pre" built is actually built by another module but AGP still
    needs to sync the gradle project before anything is built. The *build* will
    still fail if the library doesn't exist by the time it is needed, but
    that's caused by the failing copy rule.
    """
    if (error := check_build_fail_if_missing(test_dir, ndk_path, config)) is not None:
        return False, error
    if (error := check_sync_pass_if_missing(test_dir, ndk_path, config)) is not None:
        return False, error
    if (error := check_build_pass_if_present(test_dir, ndk_path, config)) is not None:
        return False, error
    return True, ""
