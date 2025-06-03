# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import logging
import shlex
import subprocess
import sys
from pathlib import Path

from .action import Action


class TestBuildAction(Action):
    """Action for building the tests with a prebuilt NDK."""

    def __init__(self, build_id: str, dist_dir: Path) -> None:
        self.build_id = build_id
        self.dist_dir = dist_dir

    def run(self) -> None:
        artifact_name = f"android-ndk-{self.build_id}-windows-x86_64.zip"
        # This would preferably just be a call to ndk.run_tests.main(), but for some
        # reason multiprocessing.Manager reinvokes ci.py when it starts up, causing the
        # build to loop. I couldn't figure out why that was happening even after
        # stepping through the stdlib with a debugger, so I'm just going to avoid that
        # problem for now. Eventually that multiprocessing.Manager will be gone
        # and replaced with asyncio anyway, so we can improve this then.
        cmd = [
            sys.executable,
            "ndk/buildtests.py",
            "--package",
            f"--dist-dir={self.dist_dir}",
            f"--ndk=out/prebuilt_cached/artifacts/ndk/{artifact_name}",
        ]
        print(f"Running {shlex.join(cmd)}")
        subprocess.run(cmd, check=True)
