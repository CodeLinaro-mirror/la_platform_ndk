# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Tests for ndk.devenv.devices."""
from __future__ import absolute_import

import unittest
from typing import List

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration, CMakeToolchainFile, WeakSymbolsConfig

from .device import Device
from .deviceconfig import DeviceConfig


class MockDevice(Device):
    def __init__(self, version: int, abis: List[Abi], supports_mte: bool) -> None:
        super().__init__(
            "",
            DeviceConfig(
                abis=tuple(abis),
                version=version,
                supports_mte=supports_mte,
                build_id="MockBuildId",
                product_name="MockDevice",
                is_debuggable=False,
                is_emulator=False,
                is_release=False,
            ),
        )


def make_test_build_configuration(abi: Abi, api: int) -> BuildConfiguration:
    # The CMake toolchain file option is irrelevant for determining device
    # compatibility.
    return BuildConfiguration(
        abi, api, CMakeToolchainFile.Default, WeakSymbolsConfig.WeakAPI
    )


class DeviceTest(unittest.TestCase):
    def test_can_run_build_config(self) -> None:
        jb_arm = MockDevice(16, [Abi("armeabi-v7a")], False)
        n_arm = MockDevice(25, [Abi("armeabi-v7a"), Abi("arm64-v8a")], False)
        n_intel = MockDevice(25, [Abi("x86"), Abi("x86_64")], False)

        jb_arm7 = make_test_build_configuration(Abi("armeabi-v7a"), 16)
        # Too old, no PIE support.
        self.assertTrue(jb_arm.can_run_build_config(jb_arm7))
        self.assertTrue(n_arm.can_run_build_config(jb_arm7))
        # Wrong ABI.
        self.assertFalse(n_intel.can_run_build_config(jb_arm7))

        l_arm7 = make_test_build_configuration(Abi("armeabi-v7a"), 21)
        # Too old.
        self.assertFalse(jb_arm.can_run_build_config(l_arm7))
        self.assertTrue(n_arm.can_run_build_config(l_arm7))
        # Wrong ABI.
        self.assertFalse(n_intel.can_run_build_config(l_arm7))

        l_arm64 = make_test_build_configuration(Abi("arm64-v8a"), 21)
        # Too old, wrong ABI.
        self.assertFalse(jb_arm.can_run_build_config(l_arm64))
        self.assertTrue(n_arm.can_run_build_config(l_arm64))
        # Wrong ABI.
        self.assertFalse(n_intel.can_run_build_config(l_arm64))

        l_intel = make_test_build_configuration(Abi("x86_64"), 21)
        # Too old, wrong ABI.
        self.assertFalse(jb_arm.can_run_build_config(l_intel))
        # Wrong ABI.
        self.assertFalse(n_arm.can_run_build_config(l_intel))
        self.assertTrue(n_intel.can_run_build_config(l_intel))

        o_arm7 = make_test_build_configuration(Abi("armeabi-v7a"), 26)
        # Too old.
        self.assertFalse(jb_arm.can_run_build_config(o_arm7))
        # Too old.
        self.assertFalse(n_arm.can_run_build_config(o_arm7))
        # Too old, wrong ABI.
        self.assertFalse(n_intel.can_run_build_config(o_arm7))

        o_arm64 = make_test_build_configuration(Abi("arm64-v8a"), 26)
        # Too old.
        self.assertFalse(jb_arm.can_run_build_config(o_arm64))
        # Too old.
        self.assertFalse(n_arm.can_run_build_config(o_arm64))
        # Too old, wrong ABI.
        self.assertFalse(n_intel.can_run_build_config(o_arm64))

        o_intel = make_test_build_configuration(Abi("x86_64"), 26)
        # Too old, wrong ABI.
        self.assertFalse(jb_arm.can_run_build_config(o_intel))
        # Too old, wrong ABI.
        self.assertFalse(n_arm.can_run_build_config(o_intel))
        # Too old.
        self.assertFalse(n_intel.can_run_build_config(o_intel))
