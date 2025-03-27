#
# Copyright (C) 2018 The Android Open Source Project
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
from __future__ import absolute_import

import glob
from pathlib import Path
from typing import List, Set

from ndk.test.buildtest.case import (
    CMakeBuildTest,
    NdkBuildTest,
    PythonBuildTest,
    ShellBuildTest,
    Test,
)
from ndk.test.spec import BuildConfiguration, CMakeToolchainFile


class TestScanner:
    """Creates a Test objects for a given test directory.

    A test scanner is used to turn a test directory into a list of Tests for
    any of the test types found in the directory.
    """

    def find_tests(self, path: Path, name: str) -> List[Test]:
        """Searches a directory for tests.

        Args:
            path: Path to the test directory.
            name: Name of the test.

        Returns: List of Tests, possibly empty.
        """
        raise NotImplementedError


class BuildTestScanner(TestScanner):
    def __init__(self, ndk_path: Path, dist: bool = True) -> None:
        self.ndk_path = ndk_path
        self.dist = dist
        self.build_configurations: Set[BuildConfiguration] = set()

    def add_build_configuration(self, spec: BuildConfiguration) -> None:
        self.build_configurations.add(spec)

    def find_tests(self, path: Path, name: str) -> List[Test]:
        # If we have a build.sh, that takes precedence over the Android.mk.
        build_sh_path = path / "build.sh"
        if build_sh_path.exists():
            return self.make_build_sh_tests(path, name)

        # Same for test.py
        test_py_path = path / "test.py"
        if test_py_path.exists():
            return self.make_test_py_tests(path, name)

        # But we can have both ndk-build and cmake tests in the same directory.
        tests: List[Test] = []
        # NB: This isn't looking for Android.mk specifically (even though on
        # that would mostly be a better test) because we have a test that
        # verifies that ndk-build still works when APP_BUILD_SCRIPT is set to
        # something _other_ than a file named Android.mk.
        mk_glob = glob.glob(str(path / "jni/*.mk"))
        if mk_glob:
            tests.extend(self.make_ndk_build_tests(path, name))

        cmake_lists_path = path / "CMakeLists.txt"
        if cmake_lists_path.exists():
            tests.extend(self.make_cmake_tests(path, name))
        return tests

    def make_build_sh_tests(self, path: Path, name: str) -> List[Test]:
        return [
            ShellBuildTest(name, path, config, self.ndk_path)
            for config in self.build_configurations
            if config.toolchain_file == CMakeToolchainFile.Default
        ]

    def make_test_py_tests(self, path: Path, name: str) -> List[Test]:
        return [
            PythonBuildTest(name, path, config, self.ndk_path)
            for config in self.build_configurations
        ]

    def make_ndk_build_tests(self, path: Path, name: str) -> List[Test]:
        return [
            NdkBuildTest(name, path, config, self.ndk_path, self.dist)
            for config in self.build_configurations
            if config.toolchain_file == CMakeToolchainFile.Default
        ]

    def make_cmake_tests(self, path: Path, name: str) -> List[Test]:
        return [
            CMakeBuildTest(name, path, config, self.ndk_path, self.dist)
            for config in self.build_configurations
        ]
