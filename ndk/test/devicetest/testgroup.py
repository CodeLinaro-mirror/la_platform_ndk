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
