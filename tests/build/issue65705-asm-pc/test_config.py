def build_unsupported(test):
    if test.config.abi != "armeabi-v7a":
        return test.config.abi
    return None
