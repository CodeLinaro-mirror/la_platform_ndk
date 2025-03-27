from typing import List


def extra_ndk_build_flags() -> List[str]:
    return [
        "APP_BUILD_SCRIPT=jni/main.mk",
        "APP_PROJECT_PATH=null",
        "NDK_OUT=obj",
        "NDK_LIBS_OUT=libs",
    ]
