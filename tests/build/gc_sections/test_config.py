from ndk.test.buildtest.case import Test
from ndk.test.spec import CMakeToolchainFile


def build_broken(test: Test) -> tuple[str | None, str | None]:
    if test.config.toolchain_file is CMakeToolchainFile.Default:
        return "new CMake toolchain", "https://github.com/android/ndk/issues/1813"
    return None, None
