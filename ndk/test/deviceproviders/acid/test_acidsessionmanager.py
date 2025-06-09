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
import asyncio
from datetime import timedelta

import pytest

from ndk.abis import Abi

from .acidsessionmanager import AcidSessionManager
from .fakeacidcli import FakeAcidCli
from .fakeaciddevice import FakeAcidDevice


class TestFindConnectedSession:
    async def test_does_not_create_new_emulators(self) -> None:
        cli = FakeAcidCli()
        assert (
            await AcidSessionManager(cli).find_connected_device(Abi("x86"), 29) is None
        )
        assert not cli.requested_leases

    async def test_finds_connected_devices(self) -> None:
        cli = FakeAcidCli()
        manager = AcidSessionManager(cli, cli.factory_for_session_manager)
        assert await manager.find_connected_device(Abi("x86"), 29) is None

        cli.connect_device(
            FakeAcidDevice("abcd", "1234", [Abi("x86"), Abi("x86_64")], 29)
        )
        await manager._update_sessions()  # pylint: disable=protected-access

        device = await manager.find_connected_device(Abi("x86"), 29)
        assert device is not None
        assert Abi("x86") in device.abis
        assert device.version == 29

    async def test_does_not_find_non_matching_devices(self) -> None:
        cli = FakeAcidCli()
        manager = AcidSessionManager(cli, cli.factory_for_session_manager)
        assert await manager.find_connected_device(Abi("x86"), 29) is None

        cli.connect_device(
            FakeAcidDevice("abcd", "1234", [Abi("x86"), Abi("x86_64")], 29)
        )
        await manager._update_sessions()  # pylint: disable=protected-access

        device = await manager.find_connected_device(Abi("x86"), 34)
        assert device is None
        device = await manager.find_connected_device(Abi("riscv64"), 29)
        assert device is None


class TestLeaseEmulator:
    async def test_attempts_lease(self) -> None:
        class AutoLeasingCli(FakeAcidCli):
            async def lease_android_emulator(self, os_version: int) -> None:
                self.connect_device(
                    FakeAcidDevice("abcd", "1234", [Abi("x86")], os_version)
                )

        cli = AutoLeasingCli()
        manager = AcidSessionManager(cli)
        await manager.lease_emulator(29)
        assert len(cli.connected) == 1
        device = list(cli.connected.values())[0]
        assert device.session_id == "abcd"
        assert device.serial == "1234"
        assert device.abis == (Abi("x86"),)
        assert device.version == 29


class TestWaitForDeviceToConnect:
    async def test_finds_connected_devices(self) -> None:
        cli = FakeAcidCli()
        cli.connect_device(
            FakeAcidDevice("abcd", "1234", [Abi("x86"), Abi("x86_64")], 29)
        )
        manager = AcidSessionManager(cli, cli.factory_for_session_manager)

        async with asyncio.timeout(0):
            device = await manager.wait_for_device_to_connect(Abi("x86"), 29)
            assert device is not None
            assert Abi("x86") in device.abis
            assert device.version == 29

    async def test_finds_eventually_connected_devices(self) -> None:
        cli = FakeAcidCli()
        manager = AcidSessionManager(cli, cli.factory_for_session_manager)

        # We need to test that a coroutine that has suspended because it reached the
        # timeout can complete once the device is connected. Using asyncio.timeout would
        # cancel the timeout and we'd rerun it, so instead we have to create a task, run
        # with a **non-canceling** timeout, then connect the device and continue.
        task = asyncio.create_task(
            manager.wait_for_device_to_connect(
                Abi("x86"), 29, poll_period=timedelta(milliseconds=50)
            )
        )
        done, _pending = await asyncio.wait([task], timeout=0.2)
        assert not done

        cli.connect_device(
            FakeAcidDevice("abcd", "1234", [Abi("x86"), Abi("x86_64")], 29)
        )
        device = await asyncio.wait_for(task, timeout=0.2)
        assert device is not None
        assert Abi("x86") in device.abis
        assert device.version == 29

    async def test_times_out_if_not_connected(self) -> None:
        cli = FakeAcidCli()
        manager = AcidSessionManager(cli, cli.factory_for_session_manager)

        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(0.2):
                await manager.wait_for_device_to_connect(
                    Abi("x86"), 29, poll_period=timedelta(milliseconds=50)
                )
