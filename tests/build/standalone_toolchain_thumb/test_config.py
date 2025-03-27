# Shut up a warning about us not being a real package.
from __future__ import absolute_import


def build_unsupported(test):
    # -mthumb is only relevant for 32-bit ARM.
    if test.config.abi != "armeabi-v7a":
        return test.config.abi
    return None
