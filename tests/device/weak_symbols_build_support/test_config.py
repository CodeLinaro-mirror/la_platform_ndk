from ndk.test.spec import WeakSymbolsConfig


def extra_cmake_flags() -> list[str]:
    return ["-DANDROID_WEAK_API_DEFS=ON"]


def build_unsupported(test) -> bool:
    # skip this test to avoid redefining __ANDROID_UNAVAILABLE_SYMBOLS_ARE_WEAK__
    if test.config.weak_symbol == WeakSymbolsConfig.WeakAPI:
        return test.config.weak_symbol
    return None
