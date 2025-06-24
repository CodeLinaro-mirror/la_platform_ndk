# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import asyncio
from pathlib import Path

from ndk.buildtests import App
from ndk.paths import get_dist_dir, get_out_dir

from .action import Action


class TestBuildAction(Action):
    """Action for building the tests with a prebuilt NDK."""

    def __init__(self, build_id: str, dist_dir: Path) -> None:
        self.build_id = build_id
        self.dist_dir = dist_dir

    def run(self) -> None:
        artifact_name = f"android-ndk-{self.build_id}-windows-x86_64.zip"
        ndk_path = Path("out/prebuilt_cached/artifacts/ndk") / artifact_name
        asyncio.run(
            App(
                ndk_path=ndk_path,
                out_dir=get_out_dir(),
                dist_dir=get_dist_dir(),
                clean=False,
                package=True,
            ).run()
        )
