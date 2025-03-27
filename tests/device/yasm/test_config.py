def build_unsupported(test):
    if test.config.abi not in ("x86", "x86_64"):
        return test.config.abi
    return None
