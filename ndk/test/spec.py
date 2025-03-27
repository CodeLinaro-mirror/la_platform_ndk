#
# Copyright (C) 2017 The Android Open Source Project
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
"""Configuration objects for describing test runs."""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import ndk.test.suites
from ndk.abis import LP32_ABIS, LP64_ABIS, Abi


@enum.unique
class CMakeToolchainFile(enum.Enum):
    Legacy = "legacy"
    Default = "new"


@enum.unique
class WeakSymbolsConfig(enum.Enum):
    WeakAPI = "weakapi"
    StrictAPI = "strictapi"


class TestOptions:
    """Configuration for how tests should be run."""

    def __init__(
        self,
        src_dir: Path,
        ndk_path: Path,
        out_dir: Path,
        test_filter: Optional[str] = None,
        clean: bool = True,
        build_report: Optional[str] = None,
        package_path: Optional[Path] = None,
    ) -> None:
        """Initializes a TestOptions object.

        Args:
            src_dir: Path to the tests.
            ndk_path: Path to the NDK to use to build the tests.
            out_dir: Test output directory.
            test_filter: Test filter string.
            clean: True if the out directory should be cleaned before building.
            build_report: Path to write a build report to, if any.
            package_path: Path (without extension) to package the tests.
        """
        self.src_dir = src_dir
        self.ndk_path = ndk_path
        self.out_dir = out_dir
        self.test_filter = test_filter
        self.clean = clean
        self.build_report = build_report
        self.package_path = package_path


class TestSpec:
    """Configuration for which tests should be run on which devices."""

    def __init__(
        self, abis: Iterable[Abi], suites: Iterable[str], devices: Dict[int, List[Abi]]
    ) -> None:
        self.abis = abis
        self.suites = suites
        self.devices = devices

    @classmethod
    def load(cls, path: Path, abis: Optional[Iterable[Abi]] = None) -> TestSpec:
        with path.open(encoding="utf-8") as config_file:
            test_config: dict[str, Any] = json.load(config_file)
        if abis is None:
            abis = test_config.get("abis", ndk.abis.ALL_ABIS)
        assert abis is not None
        suites = test_config.get("suites", ndk.test.suites.ALL_SUITES)
        devices: Dict[int, List[Abi]] = {}
        for api, device_abis in test_config["devices"].items():
            devices[int(api)] = []
            for abi in device_abis:
                devices[int(api)].append(Abi(abi))
        return cls(abis, suites, devices)


@dataclass(frozen=True)
class BuildConfiguration:
    """A configuration for a single test build.

    A TestSpec describes which BuildConfigurations should be included in a test
    run.
    """

    abi: Abi
    # This is always None for the global config while building. Each test will fill in
    # the appropriate value for the test (based on `APP_PLATFORM` or similar). It is
    # still a part of the BuildConfiguration class because we do not have separate
    # classes for build config *input* (the BuildConfiguration created by
    # TestBuilder.find_tests) and build config *output* (the result decided and
    # serialized by the test, which needs to be read when the test is later run by
    # run_tests.py).
    api: Optional[int]
    toolchain_file: CMakeToolchainFile
    weak_symbol: WeakSymbolsConfig

    def with_api(self, api: int) -> BuildConfiguration:
        """Creates a copy of this BuildConfiguration with a new API level.

        Args:
            api: The API level used by the new BuildConfiguration.

        Returns:
            A copy of this BuildConfiguration with the new API level.
        """
        return BuildConfiguration(
            abi=self.abi,
            api=api,
            toolchain_file=self.toolchain_file,
            weak_symbol=self.weak_symbol,
        )

    def __str__(self) -> str:
        return "-".join(
            [
                self.abi,
                str(self.api),
                self.toolchain_file.value,
                self.weak_symbol.value,
            ]
        )

    @property
    def is_lp32(self) -> bool:
        return self.abi in LP32_ABIS

    @property
    def is_lp64(self) -> bool:
        return self.abi in LP64_ABIS

    @staticmethod
    def from_string(config_string: str) -> BuildConfiguration:
        """Converts a string into a BuildConfiguration.

        Args:
            config_string: The string format of the test spec.

        Returns:
            TestSpec matching the given string.

        Raises:
            ValueError: The given string could not be matched to a TestSpec.
        """
        abi, _, rest = config_string.partition("-")
        if abi == "armeabi" and rest.startswith("v7a-"):
            abi += "-v7a"
            _, _, rest = rest.partition("-")
        elif abi == "arm64" and rest.startswith("v8a-"):
            abi += "-v8a"
            _, _, rest = rest.partition("-")

        api_str, toolchain_file_str, weak_symbols_str = rest.split("-")
        api = int(api_str)
        toolchain_file = CMakeToolchainFile(toolchain_file_str)
        weak_symbols = WeakSymbolsConfig(weak_symbols_str)

        return BuildConfiguration(Abi(abi), api, toolchain_file, weak_symbols)

    def get_extra_ndk_build_flags(self) -> list[str]:
        extra_flags = []
        extra_flags.append("V=1")
        if self.weak_symbol == WeakSymbolsConfig.WeakAPI:
            extra_flags.append("APP_WEAK_API_DEFS=true")

        return extra_flags

    def get_extra_cmake_flags(self) -> list[str]:
        extra_flags = []
        extra_flags.append("-DCMAKE_VERBOSE_MAKEFILE=ON")
        if self.weak_symbol == WeakSymbolsConfig.WeakAPI:
            extra_flags.append("-DANDROID_WEAK_API_DEFS=ON")
        return extra_flags
