# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration

from .adbdeviceinterface import AdbDeviceInterface
from .deviceconfig import DeviceConfig


class Device:
    """A device to be used for testing."""

    # pylint: disable=no-member
    def __init__(self, serial: str, precache: bool = False) -> None:
        self.adb = AdbDeviceInterface(serial)
        self.serial = serial
        self._did_cache = False
        self._cached_abis: list[Abi] | None = None
        self._ro_build_characteristics: str | None = None
        self._ro_build_id: str | None = None
        self._ro_build_version_sdk: str | None = None
        self._ro_build_version_codename: str | None = None
        self._ro_debuggable: str | None = None
        self._ro_product_name: str | None = None
        self._supports_mte: bool = False

        if precache:
            self.cache_properties()

    def config(self) -> DeviceConfig:
        return DeviceConfig(self.abis, self.version, self.supports_mte)

    def cache_properties(self) -> None:
        """Caches the device's system properties."""
        if not self._did_cache:
            self._ro_build_characteristics = self.adb.get_prop(
                "ro.build.characteristics"
            )
            self._ro_build_id = self.adb.get_prop("ro.build.id")
            self._ro_build_version_sdk = self.adb.get_prop("ro.build.version.sdk")
            self._ro_build_version_codename = self.adb.get_prop(
                "ro.build.version.codename"
            )
            self._ro_debuggable = self.adb.get_prop("ro.debuggable")
            self._ro_product_name = self.adb.get_prop("ro.product.name")
            self._did_cache = True

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
                value = self.adb.get_prop(abi_prop)
                if value is not None:
                    abis.update([Abi(s) for s in value.split(",")])

            if "x86_64" in abis:
                # Don't allow ndk_translation to count as an arm test device.
                # We need to verify that things work on actual Arm, not that
                # they work when binary translated for x86.
                abis.difference_update({"arm64-v8a", "armeabi-v7a"})

            self._cached_abis = sorted(list(abis))
            self._supports_mte = (
                self.adb.shell_nocheck(["grep", " mte", "/proc/cpuinfo"])[0] == 0
            )

    def shell_nocheck(self, cmd: list[str]) -> tuple[int, str, str]:
        return self.adb.shell_nocheck(cmd)

    def shell(self, cmd: list[str]) -> tuple[str, str]:
        return self.adb.shell(cmd)

    def clear_logcat(self) -> None:
        self.adb.clear_logcat()

    def logcat(self) -> str:
        return self.adb.logcat()

    def push(self, local: str | list[str], remote: str, sync: bool = False) -> str:
        return self.adb.push(local, remote, sync)

    @property
    def name(self) -> str:
        self.cache_properties()
        assert self._ro_product_name is not None
        return self._ro_product_name

    @property
    def version(self) -> int:
        self.cache_properties()
        assert self._ro_build_version_sdk is not None
        return int(self._ro_build_version_sdk)

    @property
    def abis(self) -> list[Abi]:
        """Returns a list of ABIs supported by the device."""
        self.cache_properties()
        assert self._cached_abis is not None
        return self._cached_abis

    @property
    def build_id(self) -> str:
        self.cache_properties()
        assert self._ro_build_id is not None
        return self._ro_build_id

    @property
    def is_release(self) -> bool:
        self.cache_properties()
        codename = self._ro_build_version_codename
        return codename == "REL"

    @property
    def is_emulator(self) -> bool:
        self.cache_properties()
        chars = self._ro_build_characteristics
        return chars == "emulator"

    @property
    def is_debuggable(self) -> bool:
        self.cache_properties()
        assert self._ro_debuggable is not None
        return int(self._ro_debuggable) != 0

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        return self.config().can_run_build_config(config)

    @property
    def supports_pie(self) -> bool:
        return self.version >= 16

    @property
    def supports_mte(self) -> bool:
        self.cache_properties()
        assert self._supports_mte is not None
        return self._supports_mte

    def __str__(self) -> str:
        return f"android-{self.version} {self.name} {self.serial} {self.build_id}"

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, Device)
        return self.serial == other.serial

    def __hash__(self) -> int:
        return hash(self.serial)
