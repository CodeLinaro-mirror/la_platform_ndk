import ndk.abis
from ndk.test.buildtest.case import Test


def extra_cmake_flags() -> list[str]:
    # Required for static executables.
    return ["-DANDROID_PLATFORM=latest"]


def override_runtime_minsdkversion(test: Test) -> int | None:
    # We build as latest because static executables require that, but static executables
    # are compatible with old OS versions.
    return ndk.abis.min_api_for_abi(test.config.abi)
