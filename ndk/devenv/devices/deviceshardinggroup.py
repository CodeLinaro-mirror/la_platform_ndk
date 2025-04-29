# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration
from ndk.workqueue import ShardingGroup

from .device import Device
from .deviceconfig import DeviceConfig


class DeviceShardingGroup(ShardingGroup[Device]):
    """A collection of devices that should be identical for testing purposes.

    For the moment, devices are only identical for testing purposes if they are
    the same hardware running the same build.
    """

    def __init__(
        self,
        devices: list[Device],
        abis: list[Abi],
        version: int,
        is_emulator: bool,
        is_release: bool,
        is_debuggable: bool,
        supports_mte: bool,
    ) -> None:
        self.devices = devices
        self.abis = abis
        self.version = version
        self.is_emulator = is_emulator
        self.is_release = is_release
        self.is_debuggable = is_debuggable
        self.supports_mte = supports_mte
        self.device_config = DeviceConfig(self.abis, self.version, self.supports_mte)

    @classmethod
    def with_first_device(cls, first_device: Device) -> DeviceShardingGroup:
        return DeviceShardingGroup(
            [first_device],
            sorted(first_device.abis),
            first_device.version,
            first_device.is_emulator,
            first_device.is_release,
            first_device.is_debuggable,
            first_device.supports_mte,
        )

    def __str__(self) -> str:
        return f'android-{self.version} {" ".join(self.abis)}'

    @property
    def shards(self) -> list[Device]:
        return self.devices

    def add_device(self, device: Device) -> None:
        if not self.device_matches(device):
            raise ValueError(f"{device} does not match this device group.")

        self.devices.append(device)

    def device_matches(self, device: Device) -> bool:
        if self.version != device.version:
            return False
        if self.abis != device.abis:
            return False
        if self.is_emulator != device.is_emulator:
            return False
        if self.is_release != device.is_release:
            return False
        if self.is_debuggable != device.is_debuggable:
            return False
        if self.supports_mte != device.supports_mte:
            return False
        return True

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        return self.device_config.can_run_build_config(config)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, DeviceShardingGroup)
        if self.version != other.version:
            return False
        if self.abis != other.abis:
            return False
        if self.is_emulator != other.is_emulator:
            return False
        if self.is_release != other.is_release:
            return False
        if self.is_debuggable != other.is_debuggable:
            return False
        if self.supports_mte != other.supports_mte:
            return False
        if self.devices != other.devices:
            print("devices not equal: {}, {}".format(self.devices, other.devices))
            return False
        return True

    def __hash__(self) -> int:
        return hash(
            (
                self.version,
                self.is_emulator,
                self.is_release,
                self.is_debuggable,
                tuple(self.abis),
                tuple(self.devices),
                self.supports_mte,
            )
        )
