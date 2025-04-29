# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from ndk.abis import Abi
from ndk.test.spec import BuildConfiguration


@dataclass(frozen=True)
class DeviceConfig:
    abis: list[Abi]
    version: int
    supports_mte: bool

    def can_run_build_config(self, config: BuildConfiguration) -> bool:
        assert config.api is not None
        if self.version < config.api:
            # Device is too old for this test.
            return False

        if config.abi not in self.abis:
            return False

        return True
