# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import shlex
import subprocess
import sys
from pathlib import Path

import ndk.ext.os

from .action import Action


class BuildAction(Action):
    """Action for building the NDK and its tests."""

    def __init__(self, build_id: str, dist_dir: Path, host: str | None = None) -> None:
        self.build_id = build_id
        self.dist_dir = dist_dir
        self.host = host

    def run(self) -> None:
        # This would preferably just be a call to ndk.run_tests.main(), but for some
        # reason multiprocessing.Manager reinvokes ci.py when it starts up, causing the
        # build to loop. I couldn't figure out why that was happening even after
        # stepping through the stdlib with a debugger, so I'm just going to avoid that
        # problem for now. Eventually that multiprocessing.Manager will be gone
        # and replaced with asyncio anyway, so we can improve this then.
        cmd = [
            sys.executable,
            "ndk/checkbuild.py",
            "--package",
            f"--build-number={self.build_id}",
        ]
        if self.host is not None:
            cmd.append(f"--system={self.host}")
        print(f"Running {shlex.join(cmd)}")
        with ndk.ext.os.modify_environ({"DIST_DIR": str(self.dist_dir)}):
            subprocess.run(cmd, check=True)
