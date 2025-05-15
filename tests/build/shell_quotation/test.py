#
# Copyright (C) 2022 The Android Open Source Project
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
"""Check for correct addition of shell quotes around fragile arguments."""
import json
import textwrap
from subprocess import CalledProcessError
from pathlib import Path

from ndk.test.spec import BuildConfiguration
from ndk.testing.builders import NdkBuildBuilder


def run_test(
    test_dir: Path, ndk_path: Path, config: BuildConfiguration
) -> tuple[bool, str]:
    """Checks that shell quotations are applied to a fragile argument."""
    project_path = test_dir / "project"
    fragile_flag = '-Dfooyoo="a + b"'
    fragile_argument = "APP_CFLAGS+=" + fragile_flag
    quoted_fragile_flag = "'-Dfooyoo=a + b'"

    builder = NdkBuildBuilder.from_build_config(
        project_path,
        ndk_path,
        config,
        ndk_build_flags=[fragile_argument, "compile_commands.json"],
    )
    try:
        builder.build()
    except CalledProcessError as ex:
        return False, ex.stdout

    cc_json = project_path / "compile_commands.json"
    if not cc_json.exists():
        return False, "{} does not exist".format(cc_json)

    with cc_json.open(encoding="utf-8") as cc_json_file:
        contents = json.load(cc_json_file)
    command_default = contents[0]["command"]
    command_short_local = contents[1]["command"]
    if not quoted_fragile_flag in command_default:
        return False, textwrap.dedent(
            f"""\
            {config.abi} compile_commands.json file had wrong contents for default command:
            Expected to contain: {quoted_fragile_flag}
            Actual: {command_default}"""
        )
    if not fragile_flag in command_short_local:
        return False, textwrap.dedent(
            f"""\
            {config.abi} compile_commands.json file had wrong contents for short-local command:
            Expected to contain: {fragile_flag}
            Actual: {command_short_local}"""
        )

    return True, ""
