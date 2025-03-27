#
# Copyright (C) 2022 The Android Open Source Project
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
import logging
import shlex
import traceback
from pathlib import Path, PurePosixPath
from typing import Optional, Tuple, Union

from ndk.test.config import DeviceTestConfig
from ndk.test.devices import Device, DeviceConfig
from ndk.test.spec import BuildConfiguration

AdbResult = tuple[int, str, str, str]


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def shell_nocheck_wrap_errors(device: Device, cmd: str) -> AdbResult:
    """Invokes device.shell_nocheck and wraps exceptions as failed commands."""
    repro_cmd = f"adb -s {device.serial} shell {shlex.quote(cmd)}"
    try:
        rc, stdout, stderr = device.shell_nocheck([cmd])
        return rc, stdout, stderr, repro_cmd
    except RuntimeError:
        return 1, cmd, traceback.format_exc(), repro_cmd


# TODO: Extract a common interface from this and ndk.test.case.build.Test for the
# printer.
class TestCase:
    """A device test case found in the dist directory.

    The test directory is structured as tests/dist/$CONFIG/$BUILD_SYSTEM/...
    What follows depends on the type of test case. Each discovered test case
    will have a name, a build configuration, a build system, and a device
    directory.
    """

    def __init__(
        self,
        name: str,
        test_src_dir: Path,
        config: BuildConfiguration,
        build_system: str,
        device_dir: PurePosixPath,
    ) -> None:
        self.name = name
        self.test_src_dir = test_src_dir
        self.config = config
        self.build_system = build_system
        self.device_dir = device_dir

    def check_unsupported(self, device: DeviceConfig) -> Optional[str]:
        raise NotImplementedError

    def check_broken(
        self, device: DeviceConfig
    ) -> Union[Tuple[None, None], Tuple[str, str]]:
        raise NotImplementedError

    def run(self, device: Device) -> AdbResult:
        logger().info('%s: shell_nocheck "%s"', device.name, self.cmd)
        return shell_nocheck_wrap_errors(device, self.cmd)

    @property
    def cmd(self) -> str:
        """The shell command to run on the device to execute the test case."""
        raise NotImplementedError

    @property
    def negated_cmd(self) -> str:
        """The command to execute the test case, but with the exit code flipped."""
        return f"! ( {self.cmd} )"

    def __str__(self) -> str:
        return f"{self.name} [{self.config}]"


class BasicTestCase(TestCase):
    """A test case for the standard NDK test builder.

    These tests were written specifically for the NDK and thus follow the
    layout we expect. In each test configuration directory, we have
    $TEST_SUITE/$ABI/$TEST_FILES. $TEST_FILES includes both the shared
    libraries for the test and the test executables.
    """

    def __init__(
        self,
        suite: str,
        executable: str,
        test_src_dir: Path,
        config: BuildConfiguration,
        build_system: str,
        device_dir: PurePosixPath,
    ) -> None:
        name = ".".join([suite, executable])
        super().__init__(name, test_src_dir, config, build_system, device_dir)

        self.suite = suite
        self.executable = executable

    def get_test_config(self) -> DeviceTestConfig:
        # We don't run anything in tests/build. We can safely assume that anything here
        # is in tests/device.
        test_dir = self.test_src_dir / "device" / self.suite
        return DeviceTestConfig.from_test_dir(test_dir)

    def check_unsupported(self, device: DeviceConfig) -> Optional[str]:
        return self.get_test_config().run_unsupported(self, device)

    def check_broken(
        self, device: DeviceConfig
    ) -> Union[Tuple[None, None], Tuple[str, str]]:
        return self.get_test_config().run_broken(self, device)

    @property
    def cmd(self) -> str:
        return "cd {} && LD_LIBRARY_PATH={} ./{} 2>&1".format(
            self.device_dir, self.device_dir, self.executable
        )
