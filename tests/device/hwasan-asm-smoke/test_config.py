from ndk.devenv.devices import DeviceConfig
from ndk.devenv.testrunner.case import TestCase
from ndk.test.buildtest.case import Test
from ndk.test.spec import CMakeToolchainFile


def build_unsupported(test: TestCase) -> str | None:
    if test.config.abi != "arm64-v8a":
        return f"{test.config.abi}"
    if test.config.toolchain_file is CMakeToolchainFile.Default:
        return "new CMake toolchain"
    return None


def run_unsupported(test: TestCase, device: DeviceConfig) -> str | None:
    # TODO(fmayer): add a runtime test
    return "does not run"


def extra_cmake_flags() -> list[str]:
    return ["-DANDROID_SANITIZE=hwaddress"]
