from typing import List


def extra_cmake_flags() -> List[str]:
    return ["-DCMAKE_FIND_ROOT_PATH=foobar"]
