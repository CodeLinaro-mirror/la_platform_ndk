def extra_cmake_flags():
    return ["-DANDROID_CPP_FEATURES=no-exceptions"]


def is_negative_test():
    return True
