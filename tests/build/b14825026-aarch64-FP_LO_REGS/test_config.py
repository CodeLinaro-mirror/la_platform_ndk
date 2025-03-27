def build_unsupported(test):
    if test.config.abi != "arm64-v8a":
        return test.config.abi
    return None
