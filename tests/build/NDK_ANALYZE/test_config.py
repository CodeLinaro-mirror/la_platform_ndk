from __future__ import absolute_import
import sys


def build_unsupported(_test):
    if sys.platform == "win32":
        return sys.platform
    return None
