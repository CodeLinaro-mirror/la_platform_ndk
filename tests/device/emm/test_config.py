def build_unsupported(test):
    if test.config.abi != "x86":
        return test.config.abi

    return None
