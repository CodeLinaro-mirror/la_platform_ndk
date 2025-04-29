# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Package for code which should only be run in the development environment.

Our development environment can make use of packages from PyPI such as rich and
aiohttp to proved a better development environment. We don't have access to PyPI
in CI, nor should we be relying on code from PyPI in the shipped NDK. Any tools
or code which should only be available on developer workstations belongs in this
package so it can be avoided in CI workflows and stripped from the release
artifacts.
"""
# TODO: Migrate existing development environment code to this package.
# TODO: Enforce isolation of PyPI imports outside this package.
# TODO: Strip this package from the shipped NDK.
