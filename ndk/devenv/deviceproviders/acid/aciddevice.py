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
from __future__ import annotations

from ndk.devenv.devices import Device, DeviceConfig
from ndk.devenv.devices.adbdeviceinterface import AdbDeviceInterface


class AcidDevice(Device):
    def __init__(
        self,
        session_id: str,
        serial: str,
        config: DeviceConfig,
        adb: AdbDeviceInterface | None = None,
    ) -> None:
        super().__init__(serial, config, adb)
        self.session_id = session_id

    @staticmethod
    async def create(session_id: str, serial: str) -> AcidDevice:
        adb = AdbDeviceInterface(serial)
        return AcidDevice(session_id, serial, await DeviceConfig.for_device(adb), adb)
