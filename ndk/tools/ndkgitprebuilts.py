#
# Copyright (C) 2023 The Android Open Source Project
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
"""Script for updating the prebuilt NDK installed to a git repo.

Run with `poetry run update-prebuilt-ndk`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import shlex
import shutil
import sys
import textwrap
from abc import ABC, abstractmethod
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory, mkdtemp
from typing import ContextManager

import click
from aiohttp import ClientSession

from ndk.ext.subprocess import async_run
from ndk.fetchartifact import fetch_artifact_chunked
from ndk.hosts import Host


def is_filesystem_case_sensitive(path: Path) -> bool:
    """Returns True if the file system the given path belongs to is case-sensitive."""
    if not path.exists():
        path.mkdir(parents=True)
    elif not path.is_dir():
        raise ValueError(f"{path} is not a directory")

    temp_dir = Path(mkdtemp(prefix=f"{path}/"))
    try:
        (temp_dir / "a").touch()
        return not (temp_dir / "A").exists()
    finally:
        shutil.rmtree(temp_dir)


async def run_piped(cmd: list[str], cwd: Path | None = None) -> bytes:
    """Runs and logs an asyncio subprocess.

    stdout and stderr will be combined and returned as bytes.
    """
    logging.debug("exec CWD=%s %s", cwd or Path.cwd(), shlex.join(cmd))
    proc = await asyncio.create_subprocess_exec(
        cmd[0],
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return stdout


async def run_shell(cmd: str, cwd: Path | None = None) -> None:
    """Runs and logs an asyncio subprocess."""
    logging.debug("shell CWD=%s %s", cwd or Path.cwd(), cmd)
    proc = await asyncio.create_subprocess_shell(cmd, cwd=cwd)
    await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: CWD={cwd or Path.cwd()} {cmd}")


class NdkSource(ABC):
    @abstractmethod
    def commit_summary(self) -> str: ...

    @abstractmethod
    async def download_zip(self, destination: Path) -> None: ...

    @abstractmethod
    def infer_major_version(self) -> int | None:
        """Infers the major version from the source, if possible."""

    @staticmethod
    def from_str(ndk_source: str, platform: Host) -> NdkSource:
        if ndk_source.startswith("r"):
            return ReleasedNdk(ndk_source, platform)
        if (path := Path(ndk_source)).exists():
            return ZippedNdk(path)
        return CanaryNdk(ndk_source, platform)


class ReleasedNdk(NdkSource):
    def __init__(self, version: str, platform: Host) -> None:
        super().__init__()
        self.version = version
        self.platform = platform.value

    def commit_summary(self) -> str:
        return f"Update to NDK {self.version}."

    def infer_major_version(self) -> int | None:
        pattern = r"r(\d+).*"
        if (match := re.search(pattern, self.version)) is not None:
            return int(match.group(1))
        raise ValueError(
            f"NDK version {self.version} did not match expected pattern {pattern}"
        )

    @property
    def url(self) -> str:
        return f"https://dl.google.com/android/repository/android-ndk-{self.version}-{self.platform}.zip"

    async def download_zip(self, destination: Path) -> None:
        logging.info("Downloading NDK from %s", self.url)
        async with ClientSession() as session:
            async with session.get(self.url) as response:
                with destination.open("wb") as output:
                    async for chunk in response.content.iter_chunked(4 * 1024 * 1024):
                        output.write(chunk)


class CanaryNdk(NdkSource):
    def __init__(self, build_id: str, platform: Host) -> None:
        super().__init__()
        self.build_id = build_id
        self.platform = platform.value

    def commit_summary(self) -> str:
        return f"Update to canary build {self.build_id}."

    def infer_major_version(self) -> int | None:
        return None

    async def download_zip(self, destination: Path) -> None:
        async with ClientSession() as session:
            with destination.open("wb") as output:
                async for chunk in fetch_artifact_chunked(
                    "linux",
                    self.build_id,
                    f"android-ndk-{self.build_id}-{self.platform}-x86_64.zip",
                    session,
                ):
                    output.write(chunk)


class ZippedNdk(NdkSource):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def commit_summary(self) -> str:
        return f"(DO NOT SUBMIT) Update with local NDK."

    def infer_major_version(self) -> int | None:
        return None

    async def download_zip(self, destination: Path) -> None:
        shutil.copy(self.path, destination)


class PrebuiltsRepo:
    def __init__(
        self,
        path: Path,
        ndk_major_version: int | None,
        ndk_source: NdkSource,
        platform: Host,
    ) -> None:
        self.path = path
        self.ndk_major_version = ndk_major_version
        self.ndk_source = ndk_source
        self.platform = platform

    async def prepare_for_install(self, force: bool) -> None:
        await self.ensure_latest_main(force)
        await self.remove_contents()

    async def ensure_latest_main(self, force: bool) -> None:
        """Clones or updates the NDK prebuilt repo in self.git_repo_path."""
        if (self.path / ".git").exists():
            await self.update_git_repo(force)
        else:
            await self.clone_git_repo()

    async def update_git_repo(self, force: bool) -> None:
        """Updates the NDK prebuilt repo in self.path."""
        if not force:
            await self.check_if_repo_clean()
        await self.checkout_main(force)
        if force:
            await self._git(["clean", "-df"])
        await self._git(["pull"])

    async def check_if_repo_clean(self) -> None:
        """Raises if the repository has uncommitted changes."""
        output = (await self._git_piped(["status", "--porcelain"])).decode("utf-8")
        if output:
            raise RuntimeError(
                f"Cannot update {self.path} because there are uncommitted changes or"
                f"untracked files:\n{output}"
            )

    async def checkout_main(self, force: bool) -> None:
        """Switches to the main branch."""
        args = ["checkout"]
        if force:
            args.append("-f")
        args.append("main")
        await self._git(args)

    async def clone_git_repo(self) -> None:
        """Clones the NDK prebuilt repo in self.git_repo_path."""
        assert self.ndk_major_version is not None
        repo_base = "https://android.googlesource.com/toolchain/prebuilts/ndk"
        if self.platform == Host.Darwin:
            repo_base += "-darwin"
        await async_run(
            [
                "git",
                "clone",
                f"{repo_base}/r{self.ndk_major_version}",
                str(self.path),
            ],
            check=True,
        )

    async def remove_contents(self) -> None:
        await self._git(["rm", "-rf", "--ignore-unmatch", "."])

    async def _git(self, cmd: list[str]) -> None:
        await async_run(["git", "-C", str(self.path)] + cmd, check=True)

    async def _git_piped(self, cmd: list[str]) -> bytes:
        return await run_piped(["git", "-C", str(self.path)] + cmd)

    async def install_from(self, ndk_zip: Path) -> None:
        await self.unzip_to_repo(ndk_zip)
        self.fixup_install()
        await self.create_commit()

    async def unzip_to_repo(self, ndk_zip: Path) -> None:
        assert ndk_zip.exists()
        # Not using TemporaryDirectory because we want to make sure it's on the same
        # filesystem as the repo so we can mv rather than cp.
        temp_dir = self.path / ".extract"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        try:
            await async_run(["unzip", "-d", str(temp_dir), str(ndk_zip)], check=True)
            # We should have extracted a single directory.
            subdirs = list(temp_dir.iterdir())
            assert len(subdirs) == 1
            ndk_dir = subdirs[0]
            for item in ndk_dir.iterdir():
                item.rename(self.path / item.name)
        finally:
            shutil.rmtree(temp_dir)

    def fixup_install(self) -> None:
        (self.path / "Android.mk").write_text(
            textwrap.dedent(
                """\
                # Intentionally empty to prevent loading subdir Android.mk files.
                # The distributed NDK includes a handful of Android.mk files for use
                # with ndk-build via import-module, but without an empty Android.mk at
                # the top level, the platform build system will try to use them.
                """
            )
        )

    async def create_commit(self) -> None:
        await self.install_commit_hook()
        await self._git(["add", "-A"])
        message = textwrap.dedent(
            f"""\
            {self.ndk_source.commit_summary()}

            Test: treehugger
            Bug: None
            """
        )
        await self._git(["commit", "-a", "-m", message])

    async def install_commit_hook(self) -> None:
        commit_hook_url = (
            "https://gerrit-review.googlesource.com/tools/hooks/commit-msg"
        )
        await run_shell(
            "f=`git rev-parse --git-dir`/hooks/commit-msg ; mkdir -p $(dirname $f) ; "
            f"curl -Lo $f {commit_hook_url} ; chmod +x $f",
            cwd=self.path,
        )

    async def upload(self) -> None:
        await self._git(
            ["push", "-o", "banned-words~skip", "origin", "HEAD:refs/for/main"]
        )


class App:
    def __init__(
        self,
        ndk_source: NdkSource,
        ndk_major_version: int | None,
        working_directory: Path,
        force_reset_git_repo: bool,
        platform: Host,
    ) -> None:
        self.prebuilts_repo = PrebuiltsRepo(
            working_directory / "git_repo", ndk_major_version, ndk_source, platform
        )
        self.ndk_source = ndk_source
        self.working_directory = working_directory
        self.force_reset_git_repo = force_reset_git_repo

    async def run(self) -> None:
        logging.debug("Updating prebuilt NDK at %s", self.prebuilts_repo.path)
        dest = self.working_directory / "ndk.zip"
        await asyncio.gather(
            self.ndk_source.download_zip(dest),
            self.prebuilts_repo.prepare_for_install(self.force_reset_git_repo),
        )
        await self.prebuilts_repo.install_from(dest)
        await self.prebuilts_repo.upload()

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
    @click.option(
        "--ndk-major-version",
        type=int,
        help=(
            "Major version of the NDK prebuilts. If --git-repo is not used, this will "
            "determine which version of the prebuilts to clone."
        ),
    )
    @click.option(
        "-f", "--force", is_flag=True, help="Forcibly resets the state of --git-repo."
    )
    @click.option(
        "-p",
        "--platform",
        type=click.Choice([platform.value for platform in Host], case_sensitive=False),
        default=Host.Linux.value,
        callback=lambda _, __, x: Host(x.lower()),
        help="Sets host platform to update.",
    )
    @click.argument("ndk_source")
    def main(
        working_directory: Path | None,
        verbose: int,
        ndk_source: str,
        ndk_major_version: int | None,
        force: bool,
        platform: Host,
    ) -> None:
        """Updates the NDK checked in to toolchain/prebuilts/ndk[-darwin]/$VERSION.

        NDK_SOURCE is the version of the NDK to install to prebuilts. This can be
        either an NDK version name such as r25c, which will download that release from
        dl.google.com; a build ID, which will download that canary build from
        ci.android.com; or a path to a local file, which will be used as-is. A local
        file should not be used except for testing. Only release or CI artifacts should
        ever be checked in.
        """
        log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
        logging.basicConfig(level=log_levels[min(verbose, len(log_levels) - 1)])
        ndk = NdkSource.from_str(ndk_source, platform)
        if ndk_major_version is None:
            ndk_major_version = ndk.infer_major_version()
        if ndk_major_version is None:
            sys.exit(
                "Could not determine NDK major version from NDK_SOURCE "
                "({ndk_source}) and neither --git-repo nor --ndk-major-version was "
                "used."
            )

        if working_directory is None:
            working_directory_ctx: ContextManager[Path | str] = TemporaryDirectory()
        else:
            working_directory_ctx = nullcontext(working_directory)
        with working_directory_ctx as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            if not is_filesystem_case_sensitive(temp_dir):
                sys.exit(
                    f"Working directory {temp_dir} is not case-sensitive. If your "
                    "system's temp directory is not case-sensitive, you must use "
                    "--working-directory."
                )
            asyncio.run(App(ndk, ndk_major_version, temp_dir, force, platform).run())
