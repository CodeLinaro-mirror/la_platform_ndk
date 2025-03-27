from typing import Optional

from ndk.abis import Abi
from ndk.test.devices import Device
from ndk.test.devicetest.case import TestCase


def run_broken(test: TestCase, device: Device) -> tuple[Optional[str], Optional[str]]:
    if device.version == 21 and test.config.abi == Abi("armeabi-v7a"):
        return f"{device.version}", "https://github.com/android/ndk/issues/1753"
    return None, None
