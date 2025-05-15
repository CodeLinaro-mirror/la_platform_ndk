#
# Copyright (C) 2018 The Android Open Source Project
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
"""Check for correct link order from ndk-build."""
from pathlib import Path
import re
import subprocess
from subprocess import CalledProcessError
from typing import Iterator

import ndk.hosts
from ndk.test.spec import BuildConfiguration
from ndk.testing.builders import NdkBuildBuilder


def find_public_unwind_symbols(output: str) -> Iterator[str]:
    """Returns an iterator over readelf lines with unwind symbols in them."""
    #   274: 00000000000223d8     8 FUNC    GLOBAL DEFAULT   11 _Unwind_GetIP
    # Group 1: Visibility
    # Group 2: Name
    readelf_regex = re.compile(r"^.*?(\S+)\s+\d+\s+(\S+)$")
    for line in output.splitlines():
        match = readelf_regex.match(line)
        if match is None:
            continue
        visibility, name = match.groups()
        if name.startswith("_Unwind") and visibility == "DEFAULT":
            yield name


def readelf(ndk_path: Path, host: ndk.hosts.Host, library: Path, *args: str) -> str:
    """Runs readelf, returning the output."""
    readelf_path = (
        ndk_path
        / "toolchains/llvm/prebuilt"
        / ndk.hosts.get_host_tag()
        / "bin/llvm-readelf"
    )
    if host.is_windows:
        readelf_path = readelf_path.with_suffix(".exe")

    return subprocess.run(
        [str(readelf_path), *args, str(library)],
        check=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout


def run_test(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> tuple[bool, str]:
    """Check that unwinder symbols are hidden in outputs."""
    project_path = test_dir / "project"
    builder = NdkBuildBuilder.from_build_config(project_path, ndk_path, config)
    try:
        builder.build()
    except CalledProcessError as ex:
        return False, ex.stdout

    host = ndk.hosts.get_default_host()
    library = project_path / "libs" / str(config.abi) / "libfoo.so"
    readelf_output = readelf(Path(ndk_path), host, library, "-sW")
    for symbol in find_public_unwind_symbols(readelf_output):
        return False, f"Found public unwind symbol: {symbol}"
    return True, ""
