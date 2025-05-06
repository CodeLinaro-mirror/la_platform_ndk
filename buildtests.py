# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Shortcut for ndk/buildtests.py.

This would normally be installed by pip, but we want to keep this in place in
the source directory since the buildbots expect it to be here.
"""
from ndk.buildtests import App

if __name__ == "__main__":
    App.main()
