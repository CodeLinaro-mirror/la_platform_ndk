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
from .acidcli import AcidCli
from .fakeaciddevice import FakeAcidDevice


class FakeAcidCli(AcidCli):
    def __init__(self) -> None:
        self.connected: dict[str, FakeAcidDevice] = {}
        self.requested_leases: set[int] = set()

    async def lease_android_emulator(self, os_version: int) -> None:
        self.requested_leases.add(os_version)

    async def sessions(self) -> str:
        lines = ["the header should be irrelevant"]
        for device in self.connected.values():
            lines.append(
                "    ".join(
                    [
                        "12h00m",
                        "1234",
                        f"GENERIC_PHONE:{device.version}",
                        f"http://xcid/?id={device.session_id}",
                        "N/A",
                        f"adb -s {device.serial}",
                    ]
                )
            )
        return "\n".join(lines)

    async def factory_for_session_manager(
        self, session_id: str, _serial: str
    ) -> FakeAcidDevice:
        return self.connected[session_id]

    def connect_device(self, device: FakeAcidDevice) -> None:
        if device.session_id in self.connected:
            raise KeyError(f"Double connection of device {device.session_id}")
        self.connected[device.session_id] = device

    def disconnect_device(self, device: FakeAcidDevice) -> None:
        del self.connected[device.session_id]
