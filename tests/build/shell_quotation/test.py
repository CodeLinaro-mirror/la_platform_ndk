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
"""Check for correct addition of shell quotes around fragile arguments.
"""
import json
import os
import subprocess
import sys
import textwrap

from ndk.test.spec import BuildConfiguration


def run_test(ndk_path: str, config: BuildConfiguration) -> tuple[bool, str]:
    """Checks that shell quotations are applied to a fragile argument."""
    ndk_build = os.path.join(ndk_path, "ndk-build")
    if sys.platform == "win32":
        ndk_build += ".cmd"
    project_path = "project"
    fragile_flag = '-Dfooyoo="a + b"'
    fragile_argument = "APP_CFLAGS+=" + fragile_flag
    quoted_fragile_flag = "'-Dfooyoo=a + b'"
    ndk_args = [
        f"APP_ABI={config.abi}",
        f"APP_PLATFORM=android-{config.api}",
        fragile_argument,
        "-B",
        "compile_commands.json",
    ]
    proc = subprocess.Popen(
        [ndk_build, "-C", project_path] + ndk_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
    )
    out, _ = proc.communicate()
    if proc.returncode != 0:
        return proc.returncode == 0, out

    cc_json = os.path.join(project_path, "compile_commands.json")
    if not os.path.exists(cc_json):
        return False, "{} does not exist".format(cc_json)

    with open(cc_json, encoding="utf-8") as cc_json_file:
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
