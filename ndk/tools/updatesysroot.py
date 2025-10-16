#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
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
"""Update the NDK platform prebuilts from the build server."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import textwrap
from collections.abc import Iterator
from pathlib import Path
from typing import Sequence

from ndk.ext.subprocess import async_run
from ndk.paths import ANDROID_DIR
from ndk.platforms import API_LEVEL_ALIASES, MAX_API_LEVEL, MIN_API_LEVEL

FETCH_ARTIFACT = Path("/google/data/ro/projects/android/fetch_artifact")


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def check_call(cmd: Sequence[str]) -> None:
    """subprocess.check_call with logging."""
    logger().debug("check_call `%s`", " ".join(cmd))
    subprocess.check_call(cmd)


def rmtree(path: Path) -> None:
    """shutil.rmtree with logging."""
    logger().debug("rmtree %s", path)
    shutil.rmtree(str(path))


def makedirs(path: Path) -> None:
    """os.makedirs with logging."""
    logger().debug("mkdir -p %s", path)
    path.mkdir(parents=True, exist_ok=True)


def remove(path: Path) -> None:
    """os.remove with logging."""
    logger().debug("rm %s", path)
    path.unlink()


def rename(src: Path, dst: Path) -> None:
    """os.rename with logging."""
    logger().debug("mv %s %s", src, dst)
    src.rename(dst)


async def fetch_artifact(target: str, build_id: str, name: str) -> None:
    """Fetches an artifact from the build server.

    The downloaded artifact will be written to the current working directory.
    """
    if not FETCH_ARTIFACT.exists():
        raise RuntimeError(
            f"{FETCH_ARTIFACT} does not exist. update-sysoot can only be run on gLinux "
            "machines."
        )
    destination = Path(name)
    await async_run(
        [str(FETCH_ARTIFACT), "--bid", build_id, "--target", target, name, destination],
        check=True,
    )


def remove_platform_if_out_of_range(version: int, path: Path) -> None:
    if version not in range(MIN_API_LEVEL, MAX_API_LEVEL + 1):
        logger().info(
            "Removing API level %d from %s because it is not in the range [%d, %d]",
            version,
            path,
            MIN_API_LEVEL,
            MAX_API_LEVEL,
        )
        rmtree(path)


def rename_platform(version: str, path: Path) -> None:
    new_name = API_LEVEL_ALIASES[version]
    rename_platform_to(path, path.with_name(str(new_name)))


def rename_platform_to(path: Path, new_path: Path) -> None:
    if new_path.exists():
        raise RuntimeError(
            f"Could not rename {path} to {new_path} because it already exists."
        )

    rename(path, new_path)


def remove_or_rename_codename_if_unknown(version: str, path: Path) -> None:
    if version == "current" and path.parent.name == "riscv64-linux-android":
        # Special case for the currently unsupported ABI. The libraries for riscv64 are
        # only produced for "current", but the NDK doesn't use codenames, so we install
        # that as if it were the latest API level.
        rename_platform_to(path, path.with_name(str(MAX_API_LEVEL)))
    elif version not in API_LEVEL_ALIASES:
        logger().info(
            "Removing %s from %s because it is not a known codename", version, path
        )
        rmtree(path)
    else:
        rename_platform(version, path)


def remove_or_rename_platform_directory(path: Path) -> None:
    version = path.name
    try:
        version_int = int(version)
        remove_platform_if_out_of_range(version_int, path)
        return
    except ValueError:
        remove_or_rename_codename_if_unknown(version, path)


def relocate_static_crt_objects(install_path: Path) -> None:
    """Installs the static CRT objects to the latest API level.

    The static CRT objects are only built for the current (10000) API level, since
    libc.a is also built that way. libc.a gets installed into the API-generic library
    directory by soong, but the CRT objects get installed to the "current" directory
    instead. This moves those "current" CRT objects to the same directory as libc.a.
    """
    for abi_dir in (install_path / "sysroot/usr/lib").iterdir():
        crt_name = "crtbegin_static.o"
        source = abi_dir / "current" / crt_name
        dest = abi_dir / crt_name
        source.rename(dest)


def remove_and_rename_platforms_to_match_metadata(install_path: Path) -> None:
    """Removes platforms that should not be checked in."""
    for path in iter_versioned_library_directories(install_path):
        remove_or_rename_platform_directory(path)


def iter_versioned_library_directories(parent: Path) -> Iterator[Path]:
    for path in parent.glob("sysroot/usr/lib/*/*"):
        if path.is_dir():
            yield path


def start_branch(name: str) -> None:
    """Starts a branch in the project."""
    check_call(["repo", "start", name])


def kv_arg_pair(arg: str) -> tuple[str, str]:
    """Parses a key/value argument pair."""
    error_msg = "Argument must be in format key=value, got " + arg
    try:
        key, value = arg.split("=")
    except ValueError:
        # pylint: disable=raise-missing-from
        raise argparse.ArgumentTypeError(error_msg)

    if key == "" or value == "":
        raise argparse.ArgumentTypeError(error_msg)

    return key, value


def parse_args() -> argparse.Namespace:
    """Parses and returns command line arguments."""
    parser = argparse.ArgumentParser()

    download_group = parser.add_mutually_exclusive_group()

    download_group.add_argument(
        "--download",
        action="store_true",
        default=True,
        help="Fetch artifacts from the build server. BUILD is a build number.",
    )

    download_group.add_argument(
        "--no-download",
        action="store_false",
        dest="download",
        help=("Do not download build artifacts. BUILD points to a local " "artifact."),
    )

    parser.add_argument(
        "build",
        metavar="BUILD_OR_ARTIFACT",
        help=(
            "Build number to pull from the build server, or a path to a "
            "local artifact"
        ),
    )

    parser.add_argument(
        "--branch", default="aosp-main", help="Branch to pull from the build server."
    )

    parser.add_argument(
        "-b", "--bug", default="None", help="Bug URL for commit message."
    )

    parser.add_argument(
        "--use-current-branch",
        action="store_true",
        help="Do not repo start a new branch for the update.",
    )

    return parser.parse_args()


class App:
    def __init__(
        self, build_id: str, bug: str, download: bool, use_current_branch: bool
    ) -> None:
        self.build_id = build_id
        self.bug = bug
        self.download = download
        self.use_current_branch = use_current_branch

    async def run(self) -> None:
        os.chdir(ANDROID_DIR / "prebuilts/ndk")

        if self.download:
            branch_name_suffix = self.build_id
        else:
            package = Path(self.build_id)
            branch_name_suffix = "local"
            logger().info("Using local artifact at %s", package)

        if self.download:
            await fetch_artifact("ndk", self.build_id, "ndk_platform.tar.bz2")
            package = Path("ndk_platform.tar.bz2")

        if not self.use_current_branch:
            start_branch(f"update-platform-{branch_name_suffix}")

        install_path = Path("platform")
        check_call(["git", "rm", "-r", "--ignore-unmatch", str(install_path)])
        if install_path.exists():
            rmtree(install_path)
        makedirs(install_path)

        check_call(
            ["tar", "xf", str(package), "--strip-components=1", "-C", str(install_path)]
        )

        if self.download:
            remove(package)

        # It's easier to rearrange the package here than it is in the NDK's build.
        # NOTICE is in the package root by convention, but we don't actually want
        # this whole package to be the installed sysroot in the NDK.  We have
        # $INSTALL_DIR/sysroot and $INSTALL_DIR/platforms. $INSTALL_DIR/sysroot
        # will be installed to $NDK/sysroot, but $INSTALL_DIR/platforms is used as
        # input to Platforms. Shift the NOTICE into the sysroot directory.
        rename(install_path / "NOTICE", install_path / "sysroot/NOTICE")

        relocate_static_crt_objects(install_path)
        remove_and_rename_platforms_to_match_metadata(install_path)

        check_call(["git", "add", str(install_path)])

        if self.download:
            update_msg = f"to build {self.build_id}"
        else:
            update_msg = "with local artifact"

        message = textwrap.dedent(
            f"""\
            Update NDK platform prebuilts {update_msg}.

            Test: ndk/checkbuild.py && ndk/run_tests.py
            Bug: {self.bug}
            """
        )
        check_call(["git", "commit", "-m", message])

    @staticmethod
    def main() -> None:
        """Program entry point."""
        logging.basicConfig(level=logging.DEBUG)

        args = parse_args()
        asyncio.run(
            App(args.build, args.bug, args.download, args.use_current_branch).run()
        )
