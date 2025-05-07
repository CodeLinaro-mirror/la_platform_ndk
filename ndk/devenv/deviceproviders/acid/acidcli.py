#
# Copyright (C) 2025 The Android Open Source Project
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
import asyncio
import subprocess


class AcidCli:
    async def sessions(self) -> str:
        """Returns the raw output of `acid sessions`."""
        cmd = ["acid", "sessions"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return_code = await proc.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd, out, err)
        return out.decode("utf-8")

    async def lease_android_emulator(self, os_version: int) -> None:
        cmd = ["acid", "lease_android_emulator", "GENERIC_PHONE", str(os_version)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = await proc.communicate()
        return_code = await proc.wait()
        if return_code != 0:
            # Yes, this is in stdout rather than stderr for some reason.
            if b"Cannot find a matching target for spec" in out:
                return
            raise subprocess.CalledProcessError(return_code, cmd, out, err)
