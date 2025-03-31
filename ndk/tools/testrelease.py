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
from collections.abc import AsyncIterable
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import ContextManager

import click
from aiohttp import ClientSession
from rich.console import Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from ndk.ext.subprocess import async_run
from ndk.fetchartifact import DEFAULT_CHUNK_SIZE, ArtifactDownloader
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


class RichProgressDownloader(ArtifactDownloader):
    def __init__(
        self, progress: Progress, target: str, build_id: str, artifact_name: str
    ) -> None:
        super().__init__(target, build_id, artifact_name)
        self.progress = progress
        self.progress_task: TaskID | None = None
        self.label = f"{self.target} {self.build_id} {self.artifact_name}"
        # Only needed so we can set the total on the progress bar when done if
        # the content length was never reported.
        self.total_downloaded = 0

    async def download(
        self, session: ClientSession, chunk_size: int = DEFAULT_CHUNK_SIZE
    ) -> AsyncIterable[bytes]:
        self.progress_task = self.progress.add_task(
            f"Downloading {self.label}", total=None
        )
        async for chunk in super().download(session, chunk_size):
            yield chunk
        self.progress.update(self.progress_task, total=self.total_downloaded)

    def on_artifact_size(self, size: int) -> None:
        super().on_artifact_size(size)
        if self.progress_task is None:
            raise RuntimeError(
                f"{self.label} received artifact size before download began"
            )
        self.progress.update(self.progress_task, total=size)

    def after_chunk(self, size: int) -> None:
        super().after_chunk(size)
        if self.progress_task is None:
            raise RuntimeError(f"{self.label} received chunk before download began")
        self.progress.update(self.progress_task, advance=size)
        self.total_downloaded += size


async def fetch_artifact(
    session: ClientSession,
    progress: Progress,
    target: str,
    build_id: str,
    name: str,
    destination: Path,
) -> None:
    """Fetches an artifact from the build server.

    The downloaded artifact will be written to the current working directory.
    """
    downloader = RichProgressDownloader(progress, target, build_id, name)
    with destination.open("wb") as output:
        async for chunk in downloader.download(session):
            output.write(chunk)


class App:
    def __init__(self, build_id: str, working_directory: Path) -> None:
        self.build_id = build_id
        self.working_directory = working_directory

    async def run(self) -> None:
        download_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            # "binary" means SI, for some reason.
            DownloadColumn(binary_units=True),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )
        extract_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        )

        group = Group(download_progress, extract_progress)
        with Live(group):
            async with ClientSession() as session:
                test_dirs_by_host = await asyncio.gather(
                    *(
                        self.prepare_test_dir(
                            session, download_progress, extract_progress, host
                        )
                        for host in Host
                    )
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
        self,
        session: ClientSession,
        download_progress: Progress,
        extract_progress: Progress,
        host: Host,
    ) -> tuple[Host, Path]:
        tarball = await self.download_test_artifact(session, download_progress, host)
        extracted = await self.extract(extract_progress, tarball, host)
        return host, extracted

    async def download_test_artifact(
        self, session: ClientSession, progress: Progress, host: Host
    ) -> Path:
        target = {
            Host.Darwin: "darwin_mac",
            Host.Linux: "linux",
            Host.Windows64: "win64_tests",
        }[host]

        destination = self.working_directory / host.name / TEST_ARTIFACT_NAME
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with ClientSession() as session:
            await fetch_artifact(
                session,
                progress,
                target,
                self.build_id,
                TEST_ARTIFACT_NAME,
                destination,
            )
        return destination

    async def extract(self, progress: Progress, tarball: Path, host: Host) -> Path:
        extract_dir = self.working_directory / host.name / "tests"
        if extract_dir.exists():
            rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=False)

        task_id = progress.add_task(f"Extracting {host} tests", total=None)
        await async_run(
            ["tar", "xf", tarball, "-C", extract_dir, "--strip-components=1"],
            check=True,
        )
        progress.update(task_id, total=1, completed=1)
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
