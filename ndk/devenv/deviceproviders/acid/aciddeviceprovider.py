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
import logging

from ndk.abis import Abi
from ndk.devenv.devices import Device

from ..deviceprovider import DeviceProvider
from .acidsessionmanager import AcidSessionManager


def logger() -> logging.Logger:
    return logging.getLogger(__name__)


class AcidDeviceProvider(DeviceProvider):
    def __init__(self, session_manager: AcidSessionManager | None = None) -> None:
        if session_manager is None:
            session_manager = AcidSessionManager()
        self.acid_session_manager = session_manager

    async def acquire_device(self, abi: Abi, os_version: int) -> Device | None:
        """Acquires a compatible device from ACID, leasing one if necessary.

        When a compatible device is not already connected, a new emulator will be leased
        matching the requested configuration. In the event that ACID does not provide an
        emulator with the requested ABI at the requested OS version, this call with wait
        indefinitely, so this method should be called with a timeout.
        """
        # The ABI isn't part of the ACID lease API, so it won't return an error if we
        # request something it can't provide. As of Feb 2025, ACID only provides x86 and
        # x86_64 emulators, so just check that nothing invalid is being requested before
        # continuing.
        #
        # In the event that ACID doesn't support these ABIs for the requested API level,
        # this method will wait for the device forever.
        if abi not in {Abi("x86"), Abi("x86_64")}:
            logger().warning("ACID cannot provide emulators for %s", abi)
            return None

        already_connected = await self.acid_session_manager.find_connected_device(
            abi, os_version, refresh=True
        )
        if already_connected is not None:
            return already_connected

        await self.acid_session_manager.lease_emulator(os_version)
        return await self.acid_session_manager.wait_for_device_to_connect(
            abi, os_version
        )
