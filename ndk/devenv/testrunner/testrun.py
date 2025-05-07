# Copyright (C) 2024 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0

from ndk.devenv.devices import Device, DeviceShardingGroup
from ndk.test.result import (
    ExpectedFailure,
    Failure,
    Skipped,
    Success,
    TestResult,
    UnexpectedSuccess,
)
from ndk.test.spec import BuildConfiguration

from .case import TestCase

AdbResult = tuple[int, str, str, str]


class TestRun:
    """A test case mapped to the device group it will run on."""

    def __init__(self, test_case: TestCase, device_group: DeviceShardingGroup) -> None:
        self.test_case = test_case
        self.device_group = device_group

    @property
    def name(self) -> str:
        return self.test_case.name

    @property
    def build_system(self) -> str:
        return self.test_case.build_system

    @property
    def config(self) -> BuildConfiguration:
        return self.test_case.config

    def make_result(self, adb_result: AdbResult, device: Device) -> TestResult:
        status, out, _, cmd = adb_result
        result: TestResult
        if status == 0:
            result = Success(self)
        else:
            out = "\n".join([str(device), out])
            result = Failure(self, out, cmd, self.device_group)
        return self.fixup_xfail(result, device)

    def fixup_xfail(self, result: TestResult, device: Device) -> TestResult:
        config, bug = self.test_case.check_broken(device.config())
        if config is not None:
            assert bug is not None
            if result.failed():
                assert isinstance(result, Failure)
                return ExpectedFailure(self, result.message, config, bug)
            if result.passed():
                return UnexpectedSuccess(self, config, bug)
            raise ValueError("Test result must have either failed or passed.")
        return result

    async def run(self, device: Device) -> TestResult:
        config = self.test_case.check_unsupported(device.config())
        if config is not None:
            return Skipped(self, f"test unsupported for {config}")
        return self.make_result(await self.test_case.run(device), device)

    def __str__(self) -> str:
        os_version = self.device_group.config.version
        return f"{self.name} [{self.config} running on API {os_version}]"
