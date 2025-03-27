#
# Copyright (C) 2016 The Android Open Source Project
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
"""Helper functions for NDK build and test paths."""
import os
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Optional

import ndk.config
import ndk.hosts

ANDROID_DIR = Path(__file__).resolve().parents[2]
NDK_DIR = ANDROID_DIR / "ndk"
PREBUILT_SYSROOT = ANDROID_DIR / "prebuilts/ndk/platform/sysroot"
DEVICE_TEST_BASE_DIR = PurePosixPath("/data/local/tmp/tests")


def android_path(*args: str) -> Path:
    """Returns the absolute path rooted within the top level source tree."""
    return ANDROID_DIR.joinpath(*args)


def ndk_path(*args: str) -> Path:
    """Returns the absolute path rooted within the NDK source tree."""
    return android_path("ndk", *args)


def toolchain_path(*args: str) -> Path:
    """Returns a path within the toolchain subdirectory."""
    return android_path("toolchain", *args)


def expand_path(path: Path, host: ndk.hosts.Host) -> Path:
    """Expands package definition tuple into a package name.

    >>> expand_path('llvm-{host}', Host.Linux)
    'llvm-linux-x86_64'

    >>> expand_path('platforms', Host.Linux)
    'platforms'
    """
    host_tag = ndk.hosts.host_to_tag(host)
    return Path(str(path).format(host=host_tag))


def _get_dir_from_env(default: Path, env_var: str) -> Path:
    """Returns the path to a directory specified by the environment.

    If the environment variable is not set, the default will be used. The
    directory is created if it does not exist.

    Args:
        default: The path used if the environment variable is not set.
        env_var: The environment variable that contains the path, if any.

    Returns:
        The absolute path to the directory.
    """
    path = Path(os.getenv(env_var, default))
    if not path.is_dir():
        path.mkdir(parents=True)
    return path.resolve()


def get_out_dir() -> Path:
    """Returns the out directory."""
    return _get_dir_from_env(android_path("out"), "OUT_DIR")


def get_dist_dir(out_dir: Optional[Path] = None) -> Path:
    """Returns the distribution directory.

    The contents of the distribution directory are archived on the build
    servers. Suitable for build logs and final artifacts.
    """
    if out_dir is None:
        out_dir = get_out_dir()
    return _get_dir_from_env(out_dir / "dist", "DIST_DIR")


def path_in_out(dirname: Path, out_dir: Optional[Path] = None) -> Path:
    """Returns a path within the out directory."

    Args:
        dirname: Name of the directory.
        out_dir: Optional base out directory. Inferred from $OUT_DIR if not
                 supplied. If None and $OUT_DIR is not set, will use ../out
                 relative to the NDK git project.

    Returns:
        Absolute path within the out directory.
    """
    if out_dir is None:
        out_dir = get_out_dir()
    return out_dir / dirname


def get_install_path(
    out_dir: Optional[Path] = None, host: Optional[ndk.hosts.Host] = None
) -> Path:
    """Returns the built NDK install path.

    Note that the path returned might not actually contain the NDK. The NDK may
    not actually be present if:

    * The NDK hasn't been built yet.
    * The name of the release has changed since the NDK was built.
    * out_dir is not consistent with the build.

    Args:
        out_dir: Optional base out directory. Inferred from $OUT_DIR if not
                 supplied.
        host: Returns the install path for th given host.

    Returns:
        Directory that the built NDK should be installed to.
    """
    if host is None:
        host = ndk.hosts.get_default_host()
    release_name = f"android-ndk-{ndk.config.release}"
    return path_in_out(Path(host.value) / release_name, out_dir)


def walk(
    path: Path,
    top_down: bool = True,
    on_error: Optional[Callable[[OSError], None]] = None,
    follow_links: bool = False,
    directories: bool = True,
) -> Iterator[Path]:
    """Recursively iterates through files in a directory.

    This is a pathlib equivalent of os.walk, which Python inexplicably still
    does not have in the standard library.

    Args:
        path: Directory tree to walk.
        top_down: If True, walk the tree top-down. If False, walk the tree
                  bottom-up.
        on_error: An error handling callback for any OSError raised by the
                  walk.
        follow_links: If True, walk into symbolic links that resolve to
                      directories.
        directories: If True, the walk will also yield directories.
    Yields:
        A Path for each file (and optionally each directory) in the same manner
        as os.walk.
    """
    for root, dirs, files in os.walk(
        str(path), topdown=top_down, onerror=on_error, followlinks=follow_links
    ):
        root_path = Path(root)
        if directories:
            for dir_name in dirs:
                yield root_path / dir_name
        for file_name in files:
            yield root_path / file_name
