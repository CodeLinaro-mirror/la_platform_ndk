def build_unsupported(test):
    if test.config.api < 18:
        return test.config.api
    return None


def run_unsupported(_test, device):
    if device.version < 18:
        return device.version
    return None
