#!/usr/bin/env python3
#
# Copyright (C) 2021 The Android Open Source Project
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

"""Downloads a set of Kokoro artifacts and prepares commits updating prebuilts.

The script accepts a list of Kokoro build IDs (a list of UUIDs). It downloads
each build's main archive and extracts it into the appropriate place in an
ndk-kokoro-main repo/pore checkout. It automatically creates a branch and a
commit updating each prebuilt.

The script uses the `gsutil` CLI tool from the Google Cloud SDK to download
artifacts. It first uses a `gsutil ls` command with a '**' wildcard to search
the GCS bucket for the XML manifests for the given UUIDs. These manifest paths
contain the Kokoro job name.

For the given set of build IDs, the script verifies that no two builds use
different Git SHAs for a given repository, which guards against accidentally
updating two hosts to different versions.
"""

import argparse
import glob
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import UUID
from xml.etree import ElementTree

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent

GCS_BUCKET = "ndk-kokoro-release-artifacts"


@dataclass(frozen=True)
class KokoroPrebuilt:
    title: str
    extract_path: str
    artifact_glob: str


# A map from a Kokoro job name to the paths needed for downloading and
# extracting an archive.
KOKORO_PREBUILTS: dict[str, KokoroPrebuilt] = {
    "ndk/cmake/linux_release": KokoroPrebuilt(
        title="Linux CMake",
        extract_path="prebuilts/cmake/linux-x86",
        artifact_glob="cmake-linux-*-{build_id}.zip",
    ),
    "ndk/cmake/darwin_release": KokoroPrebuilt(
        title="Darwin CMake",
        extract_path="prebuilts/cmake/darwin-x86",
        artifact_glob="cmake-darwin-*-{build_id}.zip",
    ),
    "ndk/cmake/windows_release": KokoroPrebuilt(
        title="Windows CMake",
        extract_path="prebuilts/cmake/windows-x86",
        artifact_glob="cmake-windows-*-{build_id}.zip",
    ),
    "ndk/ninja/linux_release": KokoroPrebuilt(
        title="Linux Ninja",
        extract_path="prebuilts/ninja/linux-x86",
        artifact_glob="ninja-linux-{build_id}.zip",
    ),
    "ndk/ninja/darwin_release": KokoroPrebuilt(
        title="Darwin Ninja",
        extract_path="prebuilts/ninja/darwin-x86",
        artifact_glob="ninja-darwin-{build_id}.zip",
    ),
    "ndk/ninja/windows_release": KokoroPrebuilt(
        title="Windows Ninja",
        extract_path="prebuilts/ninja/windows-x86",
        artifact_glob="ninja-windows-{build_id}.zip",
    ),
    "ndk/python3/linux_release": KokoroPrebuilt(
        title="Linux Python3",
        extract_path="prebuilts/python/linux-x86",
        artifact_glob="python3-linux-{build_id}.tar.bz2",
    ),
    "ndk/python3/darwin_release": KokoroPrebuilt(
        title="Darwin Python3",
        extract_path="prebuilts/python/darwin-x86",
        artifact_glob="python3-darwin-{build_id}.tar.bz2",
    ),
    "ndk/python3/windows_release": KokoroPrebuilt(
        title="Windows Python3",
        extract_path="prebuilts/python/windows-x86",
        artifact_glob="python3-windows-{build_id}.zip",
    ),
}


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def check_call(cmd: Sequence[str]) -> None:
    """subprocess.check_call with logging."""
    logger().info("check_call `%s`", shlex.join(cmd))
    subprocess.check_call(cmd)


def rmtree(path: Path) -> None:
    """shutil.rmtree with logging."""
    logger().info("rmtree %s", path)
    shutil.rmtree(path)


def makedirs(path: Path) -> None:
    """os.makedirs with logging."""
    logger().info("mkdir -p %s", path)
    path.mkdir(parents=True, exist_ok=True)


def in_pore_tree() -> bool:
    """Returns True if the tree is using pore instead of repo."""
    return (REPO_ROOT / ".pore").exists()


def parse_args() -> argparse.Namespace:
    """Parses and returns command line arguments."""
    parser = argparse.ArgumentParser(
        description="Downloads artifacts from Kokoro and prepares commits to "
        "update prebuilts."
    )

    parser.add_argument(
        "build_id",
        metavar="BUILD_ID",
        type=UUID,
        nargs="+",
        help=("Kokoro build ID (a UUID)"),
    )

    parser.add_argument(
        "-m", "--message", default="", help="Extra text to include in commit messsages."
    )

    parser.add_argument(
        "-b", "--bug", default="None", help="Bug URL for commit messages."
    )

    branch_group = parser.add_mutually_exclusive_group()

    branch_group.add_argument(
        "--use-current-branch",
        action="store_true",
        help="Do not repo/pore start new branches for the update.",
    )

    branch_group.add_argument(
        "--branch",
        default="update-kokoro-prebuilts",
        help="Name of branch to pass to repo/pore start.",
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Dump extra debugging information."
    )

    return parser.parse_args()


@dataclass(frozen=True)
class BuildStatus:
    job_name: str
    build_id: UUID
    gcs_path: str
    # name -> sha. (e.g. 'external/cmake' -> '86d651ddf5a1ca0ec3e4823bda800b0cea32d253')
    repos: dict[str, str]


def parse_manifest_repos(manifest_path: Path) -> dict[str, str]:
    root = ElementTree.parse(manifest_path).getroot()
    logger().debug("parsing XML manifest %s", str(manifest_path))
    result = {}
    for project in root.findall("project"):
        project_str = (
            ElementTree.tostring(project, encoding="unicode").strip()
            + f" from {manifest_path}"
        )
        path = project.get("path")
        if path is None:
            sys.exit(f"error: path attribute missing from: {project_str}")
        revision = project.get("revision")
        if revision is None:
            sys.exit(f"error: revision attribute missing from: {project_str}")
        result[path] = revision
    return result


def get_build_status(
    build_id_list: list[UUID], gsutil_cmd: str, tmp_dir: Path
) -> list[BuildStatus]:
    """Use gsutil to query build statuses of a set of build IDs."""

    # Search the GCS bucket for XML manifests matching the build IDs. Allow the
    # command to fail, because we'll do a better job of reporting missing UUIDs
    # afterwards.
    gsutil_ls_cmd = [gsutil_cmd, "ls"] + [
        f"gs://{GCS_BUCKET}/**/manifest-{x}.xml" for x in build_id_list
    ]
    logger().info("run `%s`", shlex.join(gsutil_ls_cmd))
    ls_output = subprocess.run(
        gsutil_ls_cmd, encoding="utf8", stdout=subprocess.PIPE, check=False
    )

    @dataclass(frozen=True)
    class LsLine:
        job_name: str
        gcs_path: str

    ls_info: dict[UUID, LsLine] = {}

    for ls_line in ls_output.stdout.splitlines():
        logger().debug("gsutil ls output: %s", ls_line)
        match = re.match(
            rf"(gs://{GCS_BUCKET}/prod/"
            r"(.*)/"  # Kokoro job name (e.g. ndk/cmake/linux_release)
            r"\d+/"  # build number (e.g. 17)
            r"\d+-\d+)"  # timestamp (e.g. 20211109-203945)
            r"/manifest-([0-9a-f-]+)\.xml$",
            ls_line,
        )
        if not match:
            sys.exit(f"error: could not parse `gsutil ls` line: {ls_line}")
        gcs_path, job_name, bid_str = match.groups()
        ls_info[UUID(bid_str)] = LsLine(job_name, gcs_path)

    missing = set(build_id_list) - ls_info.keys()
    if len(missing) > 0:
        sys.exit("error: build IDs not found: " + ", ".join(map(str, sorted(missing))))

    xml_paths = [f"{ls_info[bid].gcs_path}/manifest-{bid}.xml" for bid in build_id_list]
    check_call(["gsutil", "cp"] + xml_paths + [str(tmp_dir)])

    result = []
    for bid in build_id_list:
        repos = parse_manifest_repos(tmp_dir / f"manifest-{bid}.xml")
        result.append(
            BuildStatus(ls_info[bid].job_name, bid, ls_info[bid].gcs_path, repos)
        )
    return result


def validate_build_repos(builds: list[BuildStatus]) -> None:
    """Make sure that no two builds have different git SHAs for the same
    repository name."""
    repos = {}
    success = True
    for build in builds:
        for name, sha in build.repos.items():
            if name not in repos:
                repos[name] = (sha, build.build_id)
            else:
                if repos[name][0] != sha:
                    print(f"error: conflicting versions of {name} repo:")
                    print(f" - {repos[name][0]} in {repos[name][1]}")
                    print(f" - {sha} in {build.build_id}")
                    success = False
    if not success:
        sys.exit(1)

    # Print out a table of git SHAs and repository names.
    print()
    print("No conflicting repositories detected:")
    for name, (sha, _) in sorted(repos.items()):
        print(f"{sha} {name}")
    print()


def validate_job_names(builds: list[BuildStatus]) -> None:
    print("Kokoro builds to download:")
    for build in builds:
        print(f"{build.build_id} {build.job_name}")
    print()
    names = [build.job_name for build in builds]
    for name in names:
        if names.count(name) != 1:
            sys.exit(f"error: job {name} specified more than once")
        if name not in KOKORO_PREBUILTS:
            sys.exit(f"error: job {name} is not handled by this script")


def clean_dest_dir(parent: Path) -> None:
    """Remove the contents of the directory (whether tracked or untracked by
    git), but don't remove .git or .gitignore."""
    logger().info("clean_dest_dir %s", parent)
    for name in os.listdir(parent):
        if name == ".git":
            continue
        if name == ".gitignore":
            # The prebuilts/python/* directories have a .gitignore file that
            # isn't part of the Kokoro archive, but we want to preserve it when
            # updating prebuilts.
            continue
        path = parent / name
        if path.is_symlink() or path.is_file():
            os.unlink(path)
        else:
            shutil.rmtree(path)


def download_artifacts(
    builds: list[BuildStatus], gsutil_cmd: str, tmp_dir: Path
) -> list[Path]:
    """Download each build's artifact.

    Return a list of absolute paths."""
    patterns = []
    for build in builds:
        prebuilt = KOKORO_PREBUILTS[build.job_name]
        patterns.append(
            build.gcs_path
            + "/"
            + prebuilt.artifact_glob.format(build_id=build.build_id)
        )

    check_call([gsutil_cmd, "-m", "cp"] + patterns + [str(tmp_dir)])
    artifacts = []
    for pattern in patterns:
        (artifact,) = glob.glob(str(tmp_dir / os.path.basename(pattern)))
        artifacts.append(Path(artifact))

    return artifacts


def update_artifact(
    build: BuildStatus,
    archive_path: Path,
    extra_message: str,
    bug: str,
    use_current_branch: bool,
    branch_name: str,
) -> None:
    prebuilt = KOKORO_PREBUILTS[build.job_name]
    dest_path = REPO_ROOT / prebuilt.extract_path

    os.chdir(dest_path)

    if not use_current_branch:
        repo_cmd = "pore" if in_pore_tree() else "repo"
        check_call([repo_cmd, "start", branch_name])

    clean_dest_dir(dest_path)
    if archive_path.name.endswith(".tar.bz2"):
        check_call(["tar", "-xf", str(archive_path)])
    elif archive_path.name.endswith(".zip"):
        check_call(["unzip", "-q", str(archive_path)])
    else:
        sys.exit(f"error: unrecognized type of archive: {archive_path}")
    # Pass -f so that files from the archive are added even if they are listed
    # in .gitignore.
    check_call(["git", "add", "-f", "."])

    commit_msg = textwrap.dedent(
        f"""\
        Update {prebuilt.title} prebuilt

        Fusion2: http://fusion2/{build.build_id}
        GCS path: {build.gcs_path}
        Prebuilt updated using: {Path(__file__).resolve().relative_to(REPO_ROOT)}

        {extra_message}

        Test: Treehugger, Kokoro presubmit
        Bug: {bug}
        """
    )

    check_call(["git", "commit", "-m", commit_msg])


def main() -> None:
    args = parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    gsutil_cmd = shutil.which("gsutil")
    if not gsutil_cmd:
        sys.exit(
            'error: no "gsutil" in PATH. ' 'Try "apt-get install google-cloud-sdk".'
        )

    tmp_dir = REPO_ROOT / "gcs_artifacts"
    if tmp_dir.exists():
        rmtree(tmp_dir)
    makedirs(tmp_dir)

    for build_id in args.build_id:
        if args.build_id.count(build_id) != 1:
            sys.exit(f"error: build ID {build_id} is duplicated")

    builds = get_build_status(args.build_id, gsutil_cmd, tmp_dir)
    validate_build_repos(builds)
    validate_job_names(builds)
    artifacts = download_artifacts(builds, gsutil_cmd, tmp_dir)

    for build, artifact in zip(builds, artifacts):
        update_artifact(
            build,
            artifact,
            args.message,
            args.bug,
            args.use_current_branch,
            args.branch,
        )


if __name__ == "__main__":
    main()
