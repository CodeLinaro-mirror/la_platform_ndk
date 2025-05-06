# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration

from .adbdeviceinterface import AdbDeviceInterface
from .deviceconfig import DeviceConfig


class Device:
    """A device to be used for testing."""

    def __init__(
        self,
        serial: str,
        config: DeviceConfig,
        adb: AdbDeviceInterface | None = None,
    ) -> None:
        if adb is None:
            adb = AdbDeviceInterface(serial)
        else:
            assert adb.serial == serial
        self.adb = adb
        self.serial = serial
        self._config = config

    @staticmethod
    async def from_serial(serial: str) -> Device:
        adb = AdbDeviceInterface(serial)
        return Device(serial, await DeviceConfig.for_device(adb), adb)

    def config(self) -> DeviceConfig:
        return self._config

    async def shell_nocheck(self, cmd: list[str]) -> tuple[int, str, str]:
        return await self.adb.shell_nocheck(cmd)

    async def shell(self, cmd: list[str]) -> tuple[str, str]:
        return await self.adb.shell(cmd)

    async def clear_logcat(self) -> None:
        await self.adb.clear_logcat()

    async def logcat(self) -> str:
        return await self.adb.logcat()

    async def push(
        self, local: str | list[str], remote: str, sync: bool = False
    ) -> str:
        return await self.adb.push(local, remote, sync)

    @property
    def product_name(self) -> str:
        return self.config().product_name

    @property
    def version(self) -> int:
        return self.config().version

    @property
    def abis(self) -> tuple[Abi, ...]:
        """Returns a list of ABIs supported by the device."""
        return self.config().abis

    @property
    def build_id(self) -> str:
        return self.config().build_id

    @property
    def is_release(self) -> bool:
        return self.config().is_release

    @property
    def is_emulator(self) -> bool:
        return self.config().is_emulator

    @property
    def is_debuggable(self) -> bool:
        return self.config().is_debuggable

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        return self.config().can_run_build_config(config)

    @property
    def supports_pie(self) -> bool:
        return self.version >= 16

    @property
    def supports_mte(self) -> bool:
        return self.config().supports_mte

    def __str__(self) -> str:
        return (
            f"android-{self.version} {self.product_name} {self.serial} {self.build_id}"
        )

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Device)
        return self.serial == other.serial

    def __hash__(self) -> int:
        return hash(self.serial)
