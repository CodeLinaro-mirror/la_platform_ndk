def extra_cmake_flags() -> list[str]:
    return ["-DANDROID_WEAK_API_DEFS=ON"]


def is_negative_test() -> bool:
    return True
