# Copyright (C) 2024 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from ndk.test.spec import BuildConfiguration

from .case import TestCase


class TestGroup:
    def __init__(
        self, build_config: BuildConfiguration, host_path: Path, tests: list[TestCase]
    ) -> None:
        self.build_config = build_config
        self.host_path = host_path
        self.tests = tests

    def has_tests(self) -> bool:
        return bool(self.tests)
