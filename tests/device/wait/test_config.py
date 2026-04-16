from typing import Optional

from ndk.devenv.devices import Device
from ndk.devenv.testrunner.case import TestCase


def run_broken(test: TestCase, device: Device) -> tuple[Optional[str], Optional[str]]:
    # Static-executable tests are broken on old kernels, rather than by API
    # levels. Marking disabled for API 21 as the test devices for that config
    # use the old kernel.
    if test.name == "wait.test_wait-static" and device.version == 21:
        return f"{device.version}", "b/502794163"
    return None, None

