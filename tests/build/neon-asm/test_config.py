def build_unsupported(test):
    if test.config.abi != "armeabi-v7a":
        return test.config.abi
    return None


def extra_cmake_flags():
    return ["-DANDROID_ARM_NEON=ON"]
