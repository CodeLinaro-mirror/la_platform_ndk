from typing import Optional

from ndk.devenv.devices import DeviceConfig
from ndk.test.buildtest.case import Test


def run_unsupported(test: Test, _device: DeviceConfig) -> Optional[str]:
    if test.name == "fuzzer.fuzz_test":
        return "not a real test"
    return None
