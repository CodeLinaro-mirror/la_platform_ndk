def extra_cmake_flags() -> list[str]:
    return ["-DANDROID_ARM_MODE=thumb"]
