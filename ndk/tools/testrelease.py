#!/usr/bin/env python
#
# Copyright (C) 2024 The Android Open Source Project
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
"""Runs release testing for the given CI build.

Using test-release is similar to using run_tests.py, except test-release downloads the
CI-built test artifacts from ci.android.com rather than using locally-built tests. It
also will test all host platforms in a single run, whereas run_tests.py must be run once
per host.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ContextManager

import click
from aiohttp import ClientSession
from fetchartifact import fetch_artifact_chunked

from ndk.ext.subprocess import async_run
from ndk.hosts import Host
from ndk.paths import NDK_DIR

TEST_ARTIFACT_NAME = "ndk-tests.tar.bz2"


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


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


async def fetch_artifact(
    session: ClientSession, target: str, build_id: str, name: str, destination: Path
) -> None:
    """Fetches an artifact from the build server.

    The downloaded artifact will be written to the current working directory.
    """
    with destination.open("wb") as output:
        async for chunk in fetch_artifact_chunked(target, build_id, name, session):
            output.write(chunk)


class App:
    def __init__(self, build_id: str, working_directory: Path) -> None:
        self.build_id = build_id
        self.working_directory = working_directory

    async def run(self) -> None:
        async with ClientSession() as session:
            test_dirs_by_host = await asyncio.gather(
                *(self.prepare_test_dir(session, host) for host in Host)
            )

        # TODO: Refactor the guts of run_tests.py so we can run all hosts in one shot.
        # There are some idle workers at the end of each host run while a few slow tests
        # finish running. The test runner internals aren't set up to allow this right
        # now, but I don't think it needs much tweaking to be able to run all the tests
        # in one shot. At the very least we could avoid the subprocess call.
        #
        # For now though, shelling out to run_tests.py is still better than having to do
        # that by hand for every host.
        for host, test_dir in test_dirs_by_host:
            print(f"Testing {host}...")
            try:
                await async_run([NDK_DIR / "run_tests.py", test_dir], check=True)
            except Exception as ex:
                ex.add_note(f"test host: {host}")
                raise

    async def prepare_test_dir(
        self, session: ClientSession, host: Host
    ) -> tuple[Host, Path]:
        tarball = await self.download_test_artifact(session, host)
        extracted = await self.extract(tarball, host)
        return host, extracted

    async def download_test_artifact(self, session: ClientSession, host: Host) -> Path:
        target = {
            Host.Darwin: "darwin_mac",
            Host.Linux: "linux",
            Host.Windows64: "win64_tests",
        }[host]

        destination = self.working_directory / host.name / TEST_ARTIFACT_NAME
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {host} {TEST_ARTIFACT_NAME} of {self.build_id}...")
        async with ClientSession() as session:
            await fetch_artifact(
                session, target, self.build_id, TEST_ARTIFACT_NAME, destination
            )
        return destination

    async def extract(self, tarball: Path, host: Host) -> Path:
        extract_dir = self.working_directory / host.name / "tests"
        if extract_dir.exists():
            rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=False)

        print(f"Extracting {host} tests...")
        await async_run(
            ["tar", "xf", tarball, "-C", extract_dir, "--strip-components=1"],
            check=True,
        )
        return extract_dir

    @staticmethod
    @click.command()
    @click.option(
        "-v",
        "--verbose",
        count=True,
        default=0,
        help="Increase verbosity (repeatable).",
    )
    @click.option(
        "--working-directory",
        type=click.Path(file_okay=False, resolve_path=True, path_type=Path),
        help=(
            "Use the given directory as the working directory rather than a temporary "
            "directory. Will not be cleaned up on program exit."
        ),
    )
    @click.argument("build_id")
    def main(working_directory: Path | None, verbose: int, build_id: str) -> None:
        """Runs release testing BUILD_ID from ci.android.com."""
        log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
        logging.basicConfig(level=log_levels[min(verbose, len(log_levels) - 1)])

        if working_directory is None:
            working_directory_ctx: ContextManager[Path | str] = TemporaryDirectory()
        else:
            working_directory_ctx = nullcontext(working_directory)
        with working_directory_ctx as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            asyncio.run(App(build_id, temp_dir).run())
