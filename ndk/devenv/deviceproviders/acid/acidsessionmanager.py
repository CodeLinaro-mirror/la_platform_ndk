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
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta
from typing import TypeAlias

from ndk.abis import Abi

from .acidcli import AcidCli
from .aciddevice import AcidDevice

AcidDeviceFactory: TypeAlias = Callable[[str, str], Awaitable[AcidDevice]]


class AcidSessionManager:
    def __init__(
        self,
        acid_cli: AcidCli | None = None,
        device_factory: AcidDeviceFactory = AcidDevice.create,
    ) -> None:
        if acid_cli is None:
            acid_cli = AcidCli()
        self.acid_cli = acid_cli
        self.device_factory = device_factory
        self.last_scanned_devices: dict[str, AcidDevice] = {}

    async def wait_for_device_to_connect(
        self, abi: Abi, os_version: int, poll_period: timedelta = timedelta(seconds=1)
    ) -> AcidDevice:
        """Periodically polls connected acid sessions until the device connects.

        Args:
            abi: The ABI of the device to wait for.
            os_version: The OS version of the device to wait for.
            poll_period: The delay between subsequent polls of connected ACID devices.

        Returns:
            The device matching the requested config. If acid sessions reports more than
            one device matching the requested config, one will be returned arbitrarily.
        """
        while True:
            await self._update_sessions()
            if (
                matching := await self.find_connected_device(abi, os_version)
            ) is not None:
                return matching
            await asyncio.sleep(poll_period.total_seconds())

    async def find_connected_device(
        self, abi: Abi, os_version: int, refresh: bool = False
    ) -> AcidDevice | None:
        if refresh:
            await self._update_sessions()

        for device in self.last_scanned_devices.values():
            if abi in device.abis and device.version == os_version:
                return device
        return None

    async def _update_sessions(self) -> None:
        previous_devices = self.last_scanned_devices
        self.last_scanned_devices = {}
        async for session_id, adb_endpoint in self._scan_sessions():
            if session_id in previous_devices:
                self.last_scanned_devices[session_id] = previous_devices[session_id]
            else:
                self.last_scanned_devices[session_id] = await self.device_factory(
                    session_id, adb_endpoint
                )

    async def _scan_sessions(self) -> AsyncIterator[tuple[str, str]]:
        # The first line is the table header. The output looks like this:
        #
        # Remaining  Serial          Device Name          View Link                 DeviceSet    Command
        # 12h00m     56080           GENERIC_PHONE:34     http://xcid/?id=IWxgyXSg  N/A          adb -s localhost:56079
        # ...
        #
        # Those fields are not tab delimited, they're an arbitrary number of spaces, and
        # the final field also contains spaces as part of the value.
        for line in (await self.acid_cli.sessions()).splitlines()[1:]:
            if not line.strip():
                continue
            m = re.search(
                r"^\S+\s+\S+\s+\S+\s+http://xcid/\?id=(\S+)\s+\S+\s+adb -s (.*)$", line
            )
            if m is None:
                continue
            session_id = m.group(1)
            adb_endpoint = m.group(2)
            yield session_id, adb_endpoint

    async def lease_emulator(self, os_version: int) -> None:
        await self.acid_cli.lease_android_emulator(os_version)
