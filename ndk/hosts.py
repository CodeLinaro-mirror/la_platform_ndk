#
# Copyright (C) 2017 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Constants and helper functions for NDK hosts."""
from __future__ import annotations

import enum
import sys


@enum.unique
class Host(enum.Enum):
    """Enumeration of supported hosts."""

    Darwin = "darwin"
    Linux = "linux"
    # TODO: Just Windows now that we only have the one.
    Windows64 = "windows64"

    # TODO: Remove.
    @property
    def is_windows(self) -> bool:
        """Returns True if the given host is Windows."""
        return self == Host.Windows64

    @property
    def tag(self) -> str:
        return host_to_tag(self)

    @property
    def platform_tag(self) -> str:
        """Returns the tag used for this host in the platform tree.

        The NDK uses full architecture names like x86_64, whereas the platform
        has always used just x86, even for the 64-bit tools.
        """
        if self is Host.Windows64:
            # The value for this is still "windows64" since we historically
            # supported 32-bit Windows. Can clean this up if we ever fix the
            # value of the enum.
            return "windows-x86"
        return f"{self.value}-x86"

    @property
    def exe_suffix(self) -> str:
        if self is Host.Windows64:
            return ".exe"
        return ""

    @classmethod
    def current(cls) -> Host:
        """Returns the Host matching the current machine."""
        # Mypy is rather picky about how these are written. `startswith` and `==` work
        # fine, but `in` behaves differently. The pattern here comes straight from the
        # mypy docs, so better work.
        # https://mypy.readthedocs.io/en/stable/common_issues.html#version-and-platform-checks
        #
        # But of course pylint thinks we *shouldn't* do that...
        # pylint: disable=no-else-return
        if sys.platform == "linux":
            return Host.Linux
        elif sys.platform == "darwin":
            return Host.Darwin
        elif sys.platform == "win32":
            return Host.Windows64
        else:
            raise RuntimeError(f"Unsupported host: {sys.platform}")

    @classmethod
    def from_tag(cls, tag: str) -> Host:
        if tag == "darwin-x86_64":
            return Host.Darwin
        if tag == "linux-x86_64":
            return Host.Linux
        if tag == "windows-x86_64":
            return Host.Windows64
        raise ValueError(f"Unrecognized host tag: {tag}")


def get_host_tag() -> str:
    """Returns the host tag used for testing on the current host."""
    # mypy prunes unreachable code fairly aggressively with sys.platform, so if this
    # doesn't use elif mypy will actually complain that the checks after the check for
    # the OS doing the linting are unreachable. That actually does mean that mypy isn't
    # checking most of this function because it quits looking after the first condition.
    # https://github.com/python/mypy/issues/5678
    if sys.platform.startswith("linux"):  # pylint: disable=no-else-return
        return "linux-x86_64"
    elif sys.platform == "darwin":
        return "darwin-x86_64"
    elif sys.platform == "win32":
        return "windows-x86_64"
    raise ValueError("Unknown host: {}".format(sys.platform))


def host_to_tag(host: Host) -> str:
    """Returns the host tag used for NDK prebuilt directories.

    >>> host_to_tag(Host.Darwin)
    'darwin-x86_64'
    >>> host_to_tag(Host.Linux)
    'linux-x86_64'
    >>> host_to_tag(Host.Windows64)
    'windows-x86_64'
    """
    # TODO: Clean up since this can all be + -x86_64 once we rename the windows
    # value.
    if not host.is_windows:
        return host.value + "-x86_64"
    if host == Host.Windows64:
        return "windows-x86_64"
    raise NotImplementedError


def get_default_host() -> Host:
    """Returns the Host matching the current machine."""
    return Host.current()
