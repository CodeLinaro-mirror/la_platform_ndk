from ndk.abis import Abi
from ndk.test.devices import Device
from ndk.test.devicetest.case import TestCase


def run_broken(test: TestCase, _device: Device) -> tuple[str | None, str | None]:
    if test.config.abi == Abi("x86"):
        return "x86", "https://github.com/android/ndk/issues/2041"
    return None, None
