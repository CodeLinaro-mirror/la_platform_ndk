# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import logging

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration

from .device import Device
from .deviceconfig import DeviceConfig
from .deviceshardinggroup import DeviceShardingGroup


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


class DeviceFleet:
    """A collection of devices that can be used for testing."""

    def __init__(self, test_configurations: dict[int, list[Abi]]) -> None:
        """Initializes a device fleet.

        Args:
            test_configurations: Dict mapping API levels to a list of ABIs to
                test for that API level. Example:

                    {
                        15: ['armeabi', 'armeabi-v7a'],
                        16: ['armeabi', 'armeabi-v7a', 'x86'],
                    }
        """
        self.devices: dict[int, dict[Abi, DeviceShardingGroup | None]] = {}
        for api, abis in test_configurations.items():
            self.devices[int(api)] = {abi: None for abi in abis}

    def add_device(self, device: Device) -> None:
        """Fills a fleet device slot with a device, if appropriate."""
        if device.version not in self.devices:
            logger().info("Ignoring device for unwanted API level: %s", device)
            return

        same_version = self.devices[device.version]
        for abi, current_group in same_version.items():
            # This device can't fulfill this ABI.
            if abi not in device.abis:
                continue

            # Never houdini.
            if abi.startswith("armeabi") and "x86" in device.abis:
                continue

            # Anything is better than nothing.
            if current_group is None:
                self.devices[device.version][abi] = (
                    DeviceShardingGroup.with_first_device(device)
                )
                continue

            if current_group.device_matches(device):
                current_group.add_device(device)
                continue

            # The emulator images have actually been changed over time, so the
            # devices are more trustworthy.
            if current_group.config.is_emulator and not device.is_emulator:
                self.devices[device.version][abi] = (
                    DeviceShardingGroup.with_first_device(device)
                )

            # Trust release builds over pre-release builds, but don't block
            # pre-release because sometimes that's all there is.
            if not current_group.config.is_release and device.is_release:
                self.devices[device.version][abi] = (
                    DeviceShardingGroup.with_first_device(device)
                )

            # If we have a device that supports MTE, prefer that.
            if not current_group.config.supports_mte and device.supports_mte:
                self.devices[device.version][abi] = (
                    DeviceShardingGroup.with_first_device(device)
                )

    def get_unique_device_groups(self) -> set[DeviceShardingGroup]:
        groups = set()
        for version in self.get_versions():
            for abi in self.get_abis(version):
                group = self.get_device_group(version, abi)
                if group is not None:
                    groups.add(group)
        return groups

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        for device_group in self.get_unique_device_groups():
            if device_group.can_run_build_config(config):
                return True
        return False

    def get_device_group(self, version: int, abi: Abi) -> DeviceShardingGroup | None:
        """Returns the device group associated with the given API and ABI."""
        if version not in self.devices:
            return None
        if abi not in self.devices[version]:
            return None
        return self.devices[version][abi]

    def get_missing(self) -> list[DeviceShardingGroup]:
        """Describes desired configurations without available devices."""
        missing = []
        for version, abis in self.devices.items():
            for abi, group in abis.items():
                if group is None:
                    missing.append(
                        DeviceShardingGroup(
                            [],
                            DeviceConfig(
                                abis=(abi,),
                                version=version,
                                build_id="",
                                product_name="",
                                is_emulator=False,
                                is_release=True,
                                is_debuggable=False,
                                supports_mte=False,
                            ),
                        )
                    )
        return missing

    def get_versions(self) -> list[int]:
        """Returns a list of all API levels in this fleet."""
        return list(self.devices.keys())

    def get_abis(self, version: int) -> list[Abi]:
        """Returns a list of all ABIs for the given API level in this fleet."""
        return list(self.devices[version].keys())
