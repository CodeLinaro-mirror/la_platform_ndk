# Copyright (C) 2022 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import logging
import os
from collections.abc import Iterator
from pathlib import Path

from ndk.paths import DEVICE_TEST_BASE_DIR
from ndk.test.filters import TestFilter
from ndk.test.spec import BuildConfiguration, TestSpec

from .case import BasicTestCase, TestCase
from .testgroup import TestGroup
from .testrun import TestRun


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def enumerate_tests_for_build_cfg(
    test_dist_dir: Path,
    build_cfg_dir: Path,
    test_src_dir: Path,
    build_cfg: BuildConfiguration,
    test_filter: TestFilter,
) -> TestGroup:
    tests: list[TestCase] = []
    for per_build_system_dir in build_cfg_dir.iterdir():
        for test_dir in per_build_system_dir.iterdir():
            out_dir = test_dir / build_cfg.abi
            test_relpath = out_dir.relative_to(test_dist_dir)
            device_dir = DEVICE_TEST_BASE_DIR / test_relpath
            for test_file in os.listdir(out_dir):
                if test_file.endswith(".so"):
                    continue
                if test_file.endswith(".sh"):
                    continue
                if test_file.endswith(".a"):
                    test_path = out_dir / test_file
                    logger().error(
                        "Found static library in app install directory. Static "
                        "libraries should never be installed. This is a bug in "
                        "the build system: %s",
                        test_path,
                    )
                    continue
                name = ".".join([test_dir.name, test_file])
                if not test_filter.filter(name):
                    continue
                tests.append(
                    BasicTestCase(
                        test_dir.name,
                        test_file,
                        test_src_dir,
                        build_cfg,
                        per_build_system_dir.name,
                        device_dir,
                    )
                )
    return TestGroup(build_cfg, build_cfg_dir, tests)


class ConfigFilter:
    def __init__(self, test_spec: TestSpec) -> None:
        self.spec = test_spec

    def filter(self, build_config: BuildConfiguration) -> bool:
        return build_config.abi in self.spec.abis


class TestPlan:
    def __init__(self, test_spec: TestSpec, test_filter: TestFilter) -> None:
        self.test_spec = test_spec
        self.test_filter = test_filter
        self.test_groups: dict[BuildConfiguration, TestGroup] = {}

    def add_tests_from_dist_dir(self, test_dist: Path, test_src: Path) -> None:
        if self.test_groups:
            raise NotImplementedError(
                "Adding multiple test dist dirs is not yet implemented"
            )

        for build_cfg_dir in test_dist.iterdir():
            # Ignore TradeFed config files.
            if not build_cfg_dir.is_dir():
                continue
            build_cfg = BuildConfiguration.from_string(build_cfg_dir.name)
            if not self._filter_config(build_cfg):
                continue

            self.add_test_group(
                enumerate_tests_for_build_cfg(
                    test_dist,
                    build_cfg_dir,
                    test_src,
                    build_cfg,
                    self.test_filter,
                )
            )

    def has_tests(self) -> bool:
        for group in self.iter_test_groups():
            if group.has_tests():
                return True
        return False

    def add_test_group(self, test_group: TestGroup) -> None:
        if test_group.build_config in self.test_groups:
            raise KeyError(f"Duplicate test group entry for {test_group.build_config}")
        self.test_groups[test_group.build_config] = test_group

    def iter_build_configs(self) -> Iterator[BuildConfiguration]:
        yield from self.test_groups.keys()

    def iter_test_groups(self) -> Iterator[TestGroup]:
        yield from self.test_groups.values()

    def iter_test_runs(self) -> Iterator[TestRun]:
        raise NotImplementedError

    def _filter_config(self, build_config: BuildConfiguration) -> bool:
        return build_config.abi in self.test_spec.abis
