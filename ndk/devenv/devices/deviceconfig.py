# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration

from .adbdeviceinterface import AdbDeviceInterface


@dataclass(frozen=True)
class DeviceConfig:
    abis: tuple[Abi, ...]
    version: int
    supports_mte: bool
    build_id: str
    product_name: str
    is_debuggable: bool
    is_emulator: bool
    is_release: bool

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        assert config.api is not None
        if self.version < config.api:
            # Device is too old for this test.
            return False

        if config.abi not in self.abis:
            return False

        return True

    @staticmethod
    async def for_device(adb: AdbDeviceInterface) -> DeviceConfig:
        props = await adb.sysprops()
        # 64-bit devices list their ABIs differently than 32-bit devices.
        # Check all the possible places for stashing ABI info and merge
        # them.
        abi_properties = [
            "ro.product.cpu.abi",
            "ro.product.cpu.abi2",
            "ro.product.cpu.abilist",
        ]
        abis: set[Abi] = set()
        for abi_prop in abi_properties:
            value = props.get(abi_prop)
            if value is not None:
                abis.update([Abi(s) for s in value.split(",")])

        if "x86_64" in abis:
            # Don't allow ndk_translation to count as an arm test device.
            # We need to verify that things work on actual Arm, not that
            # they work when binary translated for x86.
            abis.difference_update({"arm64-v8a", "armeabi-v7a"})

        return DeviceConfig(
            abis=tuple(sorted(list(abis))),
            version=int(props["ro.build.version.sdk"]),
            supports_mte=(await adb.shell_nocheck(["grep", " mte", "/proc/cpuinfo"]))[0]
            == 0,
            build_id=props["ro.build.id"],
            product_name=props["ro.product.name"],
            is_debuggable=int(props["ro.debuggable"]) != 0,
            is_emulator=props["ro.build.characteristics"] == "emulator",
            is_release=props["ro.build.version.codename"] == "REL",
        )
