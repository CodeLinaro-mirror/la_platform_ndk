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
"""Base class for services which can provide devices for testing."""
from abc import ABC, abstractmethod

from ndk.abis import Abi
from ndk.devenv.devices import Device


class DeviceProvider(ABC):
    """Manages acquisition of devices for testing."""

    @abstractmethod
    async def acquire_device(self, abi: Abi, os_version: int) -> Device | None:
        """Acquires a device for testing.

        This call may take a very long time to complete (minutes or more). There's no
        limit on what the provider may do to acquire the device. It may contact a device
        lab for access to a device, boot or even create a new emulator, or pause and
        wait for the user to plug in a phone.

        If a device is available, it will be connected to adb before the method returns.

        Args:
            abi: The required ABI of the device. The device returned may support other
                ABIs as well.
            os_version: The API level of the device.

        Returns:
            A device matching the requested configuration, or None if none could be
            found.
        """
