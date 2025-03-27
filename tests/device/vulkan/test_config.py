def build_unsupported(test):
    # Vulkan support wasn't added until android-24
    if test.config.api < 24:
        return test.config.api

    return None
