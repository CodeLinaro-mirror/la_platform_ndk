#!/usr/bin/env python3
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
"""Generates an HTML table for the downloads page."""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# pylint: disable=design


def get_lines() -> list[str]:
    """Returns all stdin input until the first empty line."""
    lines: list[str] = []
    while True:
        line = input()
        if line.strip() == "":
            return lines
        lines.append(line)


def parse_args() -> argparse.Namespace:
    """Parses and returns command line arguments."""
    parser = argparse.ArgumentParser()

    release_type_group = parser.add_mutually_exclusive_group()

    release_type_group.add_argument(
        "--beta", action="store_true", help="Generate content for a beta release."
    )

    release_type_group.add_argument(
        "--lts", action="store_true", help="Generate content for an LTS release."
    )

    return parser.parse_args()


@dataclass(frozen=True, order=True)
class Artifact:
    sort_index: int = field(init=False, repr=True)
    host: str
    package: str
    size: int
    sha: str

    def __post_init__(self) -> None:
        sort_order = {"windows": 1, "darwin": 2, "linux": 3}
        object.__setattr__(self, "sort_index", sort_order.get(self.host, 4))

    @property
    def pretty_host(self) -> str:
        return {
            "darwin": "macOS",
            "linux": "Linux",
            "windows": "Windows",
        }[self.host]

    @classmethod
    def from_line(cls, line: str) -> Optional[Artifact]:
        # Some lines are updates to the repository.xml files used by the SDK
        # manager. We don't care about these.
        # <sha>        12,345  path/to/repository.xml
        if line.endswith(".xml") or "android-ndk" not in line:
            return None

        # Real entries look like this:
        # | android/repository/android-ndk-r26d-linux.zip  | 668556491    | fcdad75a765a46a9cf6560353f480db251d14765 |
        if not line.startswith("|"):
            logging.error("Skipping unrecognized line: %s", line)
            return None

        _, path_str, size_str, sha, _ = line.split("|")
        path = Path(path_str.strip())
        size = int(size_str.strip())

        if path.suffix == ".zip" and "darwin" in path.name:
            # Ignore. We only publish the DMG on the web page.
            return None

        return Artifact(cls.host_from_package_path(path), path.name, size, sha.strip())

    @staticmethod
    def host_from_package_path(path: Path) -> str:
        # android-ndk-$VERSION-$HOST.$EXT
        # $VERSION might contain a hyphen for beta/RC releases.
        # Split on all hyphens and join $HOST and $EXT to get the platform.
        return path.stem.split("-")[-1]


def main() -> None:
    """Program entry point."""
    args = parse_args()
    print(
        'Paste the contents of the "New files" section of the SDK update '
        "email here. Terminate with an empty line."
    )
    lines = get_lines()
    if not lines:
        sys.exit("No input.")

    # The user may have pasted the following header line:
    # SHA1                                              size  file
    if lines[0].startswith("SHA1") or lines[0].lstrip().startswith("Link"):
        lines = lines[1:]

    artifacts = []
    for line in lines:
        if (artifact := Artifact.from_line(line)) is not None:
            artifacts.append(artifact)

    # Sort the artifacts by the specific order.
    artifacts = sorted(artifacts)

    print("For GitHub:")
    print("<table>")
    print("  <tr>")
    print("    <th>Platform</th>")
    print("    <th>Package</th>")
    print("    <th>Size (Bytes)</th>")
    print("    <th>SHA1 Checksum</th>")
    print("  </tr>")
    for artifact in artifacts:
        url_base = "https://dl.google.com/android/repository/"
        package_url = url_base + artifact.package
        link = '<a href="{}">{}</a>'.format(package_url, artifact.package)

        print("  <tr>")
        print("    <td>{}</td>".format(artifact.pretty_host))
        print("    <td>{}</td>".format(link))
        print("    <td>{}</td>".format(artifact.size))
        print("    <td>{}</td>".format(artifact.sha))
        print("  </tr>")
    print("</table>")
    print()
    print("For DAC:")

    if args.beta:
        var_prefix = "ndk_beta"
    elif args.lts:
        var_prefix = "ndk_lts"
    else:
        var_prefix = "ndk"
    for artifact in artifacts:
        dac_host = {
            "darwin": "mac64_dmg",
            "linux": "linux64",
            "windows": "win64",
        }[artifact.host]
        print()
        print("{{# {} #}}".format(artifact.pretty_host))
        print(
            "{{% setvar {}_{}_download %}}{}{{% endsetvar %}}".format(
                var_prefix, dac_host, artifact.package
            )
        )
        print(
            "{{% setvar {}_{}_bytes %}}{}{{% endsetvar %}}".format(
                var_prefix, dac_host, artifact.size
            )
        )
        print(
            "{{% setvar {}_{}_checksum %}}{}{{% endsetvar %}}".format(
                var_prefix, dac_host, artifact.sha
            )
        )


if __name__ == "__main__":
    main()
