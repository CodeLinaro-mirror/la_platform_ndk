def build_unsupported(test):
    if test.config.api < 12:
        return test.config.api
    return None
