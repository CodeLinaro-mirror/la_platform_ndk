#
# Copyright (C) 2025 The Android Open Source Project
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

from pytest import LogCaptureFixture

from ndk.abis import Abi

from .aciddeviceprovider import AcidDeviceProvider
from .acidsessionmanager import AcidSessionManager
from .fakeacidcli import FakeAcidCli
from .fakeaciddevice import FakeAcidDevice


class TestAcidDeviceProvider:
    async def test_finds_already_connected_device_immediately(self) -> None:
        cli = FakeAcidCli()
        session_manager = AcidSessionManager(cli, cli.factory_for_session_manager)
        cli.connect_device(FakeAcidDevice("abcd", "1234", [Abi("x86")], 21))
        provider = AcidDeviceProvider(session_manager)

        device = await provider.acquire_device(Abi("x86"), 21)
        assert device is not None
        assert device.serial == "1234"
        assert not cli.requested_leases

    async def test_does_not_find_disconnected_devices(self) -> None:
        cli = FakeAcidCli()
        session_manager = AcidSessionManager(cli, cli.factory_for_session_manager)
        first_device = FakeAcidDevice("first", "1234", [Abi("x86")], 21)
        cli.connect_device(first_device)
        provider = AcidDeviceProvider(session_manager)

        # Acquire the device once before disconnecting it so we know it's been
        # discovered by the provider and session manager.
        device = await provider.acquire_device(Abi("x86"), 21)
        assert device is not None
        assert device.serial == "1234"

        # Then disconnect and try to reacquire. We connect a second device because
        # `acquire_device()` will block until the device is connected, and it's simpler
        # to just connect another here than to pause and resume the coroutine to connect
        # it later.
        cli.disconnect_device(first_device)
        second_device = FakeAcidDevice("second", "5678", [Abi("x86")], 21)
        cli.connect_device(second_device)
        device = await provider.acquire_device(Abi("x86"), 21)
        assert device is not None
        assert device.serial == "5678"

    async def test_leases_missing_devices(self) -> None:
        class AutoLeasingCli(FakeAcidCli):
            async def lease_android_emulator(self, os_version: int) -> None:
                self.connect_device(
                    FakeAcidDevice("abcd", "1234", [Abi("x86")], os_version)
                )

        cli = AutoLeasingCli()
        session_manager = AcidSessionManager(cli, cli.factory_for_session_manager)
        provider = AcidDeviceProvider(session_manager)

        device = await provider.acquire_device(Abi("x86"), 21)
        assert device is not None
        assert device.serial == "1234"

    async def test_rejects_incompatible_devices(
        self, caplog: LogCaptureFixture
    ) -> None:
        session_manager = AcidSessionManager()
        provider = AcidDeviceProvider(session_manager)

        assert await provider.acquire_device(Abi("arm64-v8a"), 21) is None
        assert "ACID cannot provide emulators for arm64-v8a" in caplog.text
