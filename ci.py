# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""CI entry point.

This script is run by ci.sh (or ci.ps1) in the root of this git repo. All our CI
actions run through this entry point.
"""
from ndk.ci.app import App

App().run()
