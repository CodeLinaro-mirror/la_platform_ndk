# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CiConfig:
    """The CI configuration set by the builder."""

    target: str
    build_id: str
    dist_dir: Path

    @staticmethod
    def from_argv(argv: Sequence[str] | None = None) -> CiConfig:
        """Parses a CI configuration from command line arguments."""
        parser = ArgumentParser()

        parser.add_argument("--target", required=True, help="Target name")
        parser.add_argument("--build-id", required=True, help="Build ID")
        parser.add_argument(
            "--dist-dir",
            type=Path,
            required=True,
            help="Directory for build artifacts",
        )

        args = parser.parse_args(argv)

        return CiConfig(args.target, args.build_id, args.dist_dir)
