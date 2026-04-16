from typing import Optional

import ndk.abis
from ndk.devenv.devices import Device
from ndk.devenv.testrunner.case import TestCase
from ndk.test.buildtest.case import Test


def extra_cmake_flags() -> list[str]:
    # Required for static executables.
    return ["-DANDROID_PLATFORM=latest"]


def override_runtime_minsdkversion(test: Test) -> int | None:
    # We build as latest because static executables require that, but static executables
    # are compatible with old OS versions.
    return ndk.abis.min_api_for_abi(test.config.abi)


def run_broken(test: TestCase, device: Device) -> tuple[Optional[str], Optional[str]]:
    # Static-executable tests are broken on old kernels, rather than by API
    # levels. Marking disabled for API 21 as the test devices for that config
    # use the old kernel.
    if device.version == 21:
        return f"{device.version}", "b/502794163"
    return None, None

