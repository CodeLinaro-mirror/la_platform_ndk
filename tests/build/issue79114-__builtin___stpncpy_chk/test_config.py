def build_unsupported(test):
    if test.config.api < 21:
        return test.config.api
    return None
