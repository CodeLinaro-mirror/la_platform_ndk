#
# Copyright (C) 2023 The Android Open Source Project
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
import textwrap
from pathlib import Path


class NdkVersionHeaderGenerator:
    def __init__(
        self, major: int, minor: int, beta: int, build_number: int, canary: bool
    ) -> None:
        self.major = major
        self.minor = minor
        self.beta = beta
        self.build_number = build_number
        self.canary = canary

    def generate_str(self) -> str:
        canary = 1 if self.canary else 0
        return textwrap.dedent(
            f"""\
            #pragma once

            /**
             * Set to 1 if this is an NDK, unset otherwise. See
             * https://android.googlesource.com/platform/bionic/+/master/docs/defines.md.
             */
            #define __ANDROID_NDK__ 1

            /**
             * Major version of this NDK.
             *
             * For example: 16 for r16.
             */
            #define __NDK_MAJOR__ {self.major}

            /**
             * Minor version of this NDK.
             *
             * For example: 0 for r16 and 1 for r16b.
             */
            #define __NDK_MINOR__ {self.minor}

            /**
             * Set to 0 if this is a release build, or 1 for beta 1,
             * 2 for beta 2, and so on.
             */
            #define __NDK_BETA__ {self.beta}

            /**
             * Build number for this NDK.
             *
             * For a local development build of the NDK, this is 0.
             */
            #define __NDK_BUILD__ {self.build_number}

            /**
             * Set to 1 if this is a canary build, 0 if not.
             */
            #define __NDK_CANARY__ {canary}
            """
        )

    def write(self, output: Path) -> None:
        output.write_text(self.generate_str())
