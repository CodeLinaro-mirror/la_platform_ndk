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
"""Helper class for building CRT objects."""
import logging
import shlex
import shutil
import subprocess
from pathlib import Path

import ndk.config
import ndk.ext.subprocess
from ndk.platforms import ALL_API_LEVELS, MAX_API_LEVEL

from .abis import Abi, abi_to_triple, clang_target, iter_abis_for_api
from .paths import ANDROID_DIR, NDK_DIR


def logger() -> logging.Logger:
    return logging.getLogger(__name__)


class CrtObjectBuilder:
    """Builder for NDK CRT objects."""

    PREBUILTS_PATH = ANDROID_DIR / "prebuilts/ndk/platform"

    def __init__(self, llvm_path: Path, build_dir: Path, build_id: int) -> None:
        self.llvm_path = llvm_path
        self.build_dir = build_dir
        self.build_id = build_id
        self.artifacts: list[tuple[Abi, int, Path]] = []

    def llvm_tool(self, tool: str) -> Path:
        """Returns the path to the given LLVM tool."""
        return self.llvm_path / "bin" / tool

    def check_elf_note(self, obj_file: Path) -> None:
        """Verifies that the object file contains the expected note."""
        # readelf is a cross platform tool, so arch doesn't matter.
        readelf = self.llvm_tool("llvm-readelf")
        out = subprocess.run(
            [readelf, "--notes", obj_file], check=True, text=True, capture_output=True
        ).stdout
        if "Android" not in out:
            raise RuntimeError(f"{obj_file} does not contain NDK ELF note")

    def build_crt_brand(
        self, dest: Path, api: int, abi: Abi, build_number: int
    ) -> None:
        cc_args = [
            str(self.llvm_tool("clang")),
            "-target",
            clang_target(abi, api),
            f"-DPLATFORM_SDK_VERSION={api}",
            f'-DABI_NDK_VERSION="{ndk.config.release}"',
            f'-DABI_NDK_BUILD_NUMBER="{build_number}"',
            "-fpic",
            "-Wl,-r",
            "-no-pie",
            "-nostdlib",
            "-o",
            str(dest),
            str(NDK_DIR / "sources/crt/crtbrand.S"),
        ]

        logger().debug("Running: %s", shlex.join(cc_args))
        subprocess.run(cc_args, check=True, capture_output=True)

    def strip_platform_brand(self, dest: Path, obj_to_strip: Path) -> None:
        strip_args = [
            str(self.llvm_tool("llvm-strip")),
            # The platform build defaults to DWARF 5 even though Clang doesn't
            # for Android targets. This means that the CRT objects we get from
            # the sysroot have DWARF 5 debug info even though app code will be
            # built with DWARF 4. Studio's APK debugger isn't capable of
            # processing DWARF 5 and will discard the entire library if it
            # encounters any DWARF 5 info in the library. Studio should be fixed so we
            # can adopt DWARF 5, but for now, just strip the debug info from the CRT
            # objects. It's probably not all that useful anyway.
            #
            # Note: this currently only strips crtbegin variants, not crtend,
            # because this function is only ever called on crtbegin because
            # those are the objects that get branded. That's okay because the
            # crtend objects don't have debug info anyway. If crtend gains any
            # debug info before Studio is fixed, this workaround will need to be
            # altered to strip all the CRT objects and not just crtbegin.
            #
            # When this is later resolved, --strip-debug should be replaced here
            # by --no-strip-all.
            #
            # http://b/465649511
            "--strip-debug",
            "--remove-section=.note.android.ident",
            "-o",
            str(dest),
            str(obj_to_strip),
        ]

        logger().debug("Running: %s", shlex.join(strip_args))
        subprocess.run(strip_args, check=True, capture_output=True)

    def brand_object(self, dest: Path, obj_to_brand: Path, crtbrand_o: Path) -> None:
        ld_args = [
            str(self.llvm_tool("ld.lld")),
            "-r",
            "-o",
            str(dest),
            str(obj_to_brand),
            str(crtbrand_o),
        ]

        logger().debug("Running: %s", shlex.join(ld_args))
        subprocess.run(ld_args, check=True, capture_output=True)

    def build_crt_objects(
        self,
        build_dir: Path,
        api: int,
        abi: Abi,
        build_number: int,
    ) -> None:
        crt_brand_o = build_dir / "crtbrand.o"
        self.build_crt_brand(crt_brand_o, api, abi, build_number)
        branded_objects = {"crtbegin_dynamic.o", "crtbegin_so.o", "crtbegin_static.o"}
        for name_to_brand in branded_objects:
            is_crtbegin_static = name_to_brand == "crtbegin_static.o"
            if is_crtbegin_static and api != MAX_API_LEVEL:
                # Only the max API level has a crtbegin_static.o because there's only a
                # libc.a for that API level.
                continue

            object_dir = self.PREBUILTS_PATH / "sysroot/usr/lib" / abi_to_triple(abi)
            if not is_crtbegin_static:
                object_dir /= str(api)

            path_to_brand = object_dir / name_to_brand
            branded = build_dir / name_to_brand

            # The CRT objects from the platform have their own brands applied which are
            # redundant, and possibly inconsistent, with ours. Strip
            intermediate = branded.with_suffix(".o.stripped")
            self.strip_platform_brand(intermediate, path_to_brand)

            self.brand_object(branded, intermediate, crt_brand_o)
            self.check_elf_note(branded)
            self.artifacts.append((abi, api, branded))

    def build(self) -> None:
        self.artifacts = []
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)

        with ndk.ext.subprocess.verbose_subprocess_errors():
            for api in ALL_API_LEVELS:
                for abi in iter_abis_for_api(api):
                    dst_dir = self.build_dir / abi_to_triple(abi) / str(api)
                    dst_dir.mkdir(parents=True, exist_ok=True)
                    self.build_crt_objects(dst_dir, api, abi, self.build_id)
