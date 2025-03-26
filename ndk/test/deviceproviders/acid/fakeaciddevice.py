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
from ndk.abis import Abi

from .aciddevice import AcidDevice


class FakeAcidDevice(AcidDevice):
    def __init__(
        self,
        session_id: str,
        serial: str,
        abis: list[Abi],
        os_version: int,
    ) -> None:
        super().__init__(session_id, serial, precache=False)
        self._abis = abis
        self._os_version = os_version

    @property
    def abis(self) -> list[Abi]:
        return self._abis

    @property
    def version(self) -> int:
        return self._os_version
