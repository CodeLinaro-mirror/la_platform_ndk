from typing import Optional

from ndk.test.buildtest.case import Test
from ndk.test.devices import DeviceConfig


def run_unsupported(test: Test, _device: DeviceConfig) -> Optional[str]:
    if test.name == "fuzzer.fuzz_test":
        return "not a real test"
    return None
