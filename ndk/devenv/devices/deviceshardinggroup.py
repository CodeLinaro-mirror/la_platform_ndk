# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from ndk.test.spec import BuildConfiguration

from .device import Device
from .deviceconfig import DeviceConfig


class DeviceShardingGroup:
    """A collection of devices that should be identical for testing purposes.

    For the moment, devices are only identical for testing purposes if they are
    the same hardware running the same build.
    """

    def __init__(self, devices: list[Device], config: DeviceConfig) -> None:
        self.devices = devices
        self.config = config

    @classmethod
    def with_first_device(cls, first_device: Device) -> DeviceShardingGroup:
        return DeviceShardingGroup([first_device], first_device.config())

    def __str__(self) -> str:
        return f'android-{self.config.version} {" ".join(self.config.abis)}'

    @property
    def shards(self) -> list[Device]:
        return self.devices

    def add_device(self, device: Device) -> None:
        if not self.device_matches(device):
            raise ValueError(f"{device} does not match this device group.")

        self.devices.append(device)

    def device_matches(self, device: Device) -> bool:
        return self.config == device.config()

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        return self.config.can_run_build_config(config)

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, DeviceShardingGroup)
        if self.config != other.config:
            return False
        if self.devices != other.devices:
            print("devices not equal: {}, {}".format(self.devices, other.devices))
            return False
        return True

    def __hash__(self) -> int:
        return hash(self.config)
