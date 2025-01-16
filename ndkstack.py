#!/usr/bin/env python3
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
"""Symbolizes stack traces from logcat.
See https://developer.android.com/ndk/guides/ndk-stack for more information.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import BinaryIO

EXE_SUFFIX = ".exe" if os.name == "nt" else ""


class TmpDir:
    """Manage temporary directory creation."""

    def __init__(self) -> None:
        self._tmp_dir: Path | None = None

    def delete(self) -> None:
        if self._tmp_dir:
            shutil.rmtree(self._tmp_dir)

    def get_directory(self) -> Path:
        if not self._tmp_dir:
            self._tmp_dir = Path(tempfile.mkdtemp())
        return self._tmp_dir


class BuildIdReader(ABC):
    @abstractmethod
    def build_id(self, path: Path) -> bytes | None:
        """Returns the build ID of the given file, or None if none was found."""


class Readelf(BuildIdReader):
    def __init__(self, path: Path) -> None:
        self.path = path

    def build_id(self, path: Path) -> bytes | None:
        return get_build_id(self.path, path)


class NullBuildIdReader(BuildIdReader):
    def build_id(self, path: Path) -> bytes | None:
        return None


class SymbolSource(ABC):
    """A source of debug symbols.

    A symbol source may be an APK, a native-debug-symbols.zip files (the
    artifact of debug symbols that is uploaded to Play), an ELF file, or a
    directory containing other symbol sources.
    """

    @abstractmethod
    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        """Finds an ELF file which provides debug info for the given frame.

        Args:
            frame_info: The frame to find debug info for.

        Returns:
            The path of an ELF file which provides debug info for the given frame if one
            is found in this symbol source. Returns None if no matching file was found.
        """


class ElfSymbolSource(SymbolSource):
    """An ELF file containing debug symbols."""

    def __init__(
        self, path: Path, display_path: str, build_id_reader: BuildIdReader
    ) -> None:
        self.path = path
        self.display_path = display_path
        self.build_id_reader = build_id_reader

    @cached_property
    def build_id(self) -> bytes | None:
        return self.build_id_reader.build_id(self.path)

    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        # TODO: Accept matching build IDs even if the file names don't match.
        # This is probably the wrong order of precedence, but it's the pre-existing
        # behavior.
        if frame_info.elf_file is None:
            # The trace frame named a container and an offset but not the file name. We
            # can't find the file until that's been found by parsing the container,
            # which will be done by the container specific SymbolSource.
            return None
        if self.path.name != frame_info.elf_file.name:
            return None
        if frame_info.build_id is not None and self.build_id is not None:
            if self.build_id_matches(frame_info.build_id):
                return self.path
            return None
        return self.path

    def build_id_matches(self, build_id: bytes) -> bool:
        """Returns True if the build ID of the ELF file matches the frame info."""
        if self.build_id is None:
            print(f"ERROR: Could not determine build ID for {self.path}", flush=True)
            return False
        if build_id != self.build_id:
            print(f"WARNING: Mismatched build id for {self.display_path}", flush=True)
            print(f"WARNING:   Expected {build_id.decode('utf-8')}", flush=True)
            print(f"WARNING:   Found    {self.build_id.decode('utf-8')}", flush=True)
            return False
        return True


class ApkSymbolSource(SymbolSource):
    def __init__(
        self, path: Path, build_id_reader: BuildIdReader, temp_dir: Path
    ) -> None:
        self.path = path
        self.build_id_reader = build_id_reader
        self.temp_dir = temp_dir

    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        # This matches a file format such as Base.apk!libsomething.so
        with zipfile.ZipFile(self.path) as zip_file:
            assert frame_info.offset is not None
            zip_info = get_zip_info_from_offset(zip_file, frame_info.offset)
            if not zip_info:
                return None
            elf_file_path = Path(zip_file.extract(zip_info, self.temp_dir))
            display_elf_file = f"{self.path}!{frame_info.elf_file.name}"
            source = ElfSymbolSource(
                elf_file_path, display_elf_file, self.build_id_reader
            )
            if (provider := source.find_providing_elf_file(frame_info)) is not None:
                return provider
            return None


# TODO: Delete once the refactor is done.
# This is a crutch to keep the mock-heavy tests working before they can be replaced.
def find_elf_in_apk(
    path: Path, frame_info: FrameInfo, temp_dir: Path, build_id_reader: BuildIdReader
) -> Path | None:
    return ApkSymbolSource(path, build_id_reader, temp_dir).find_providing_elf_file(
        frame_info
    )


def get_ndk_paths() -> tuple[Path, Path, str]:
    """Parse and find all of the paths of the ndk

    Returns: Three values:
             Full path to the root of the ndk install.
             Full path to the ndk bin directory where this executable lives.
             The platform name (eg linux-x86_64).
    """

    # ndk-stack is installed as a zipped Python application (created with zipapp). The
    # behavior of __file__ when Python runs a zip file doesn't appear to be documented,
    # but experimentally for this case it will be:
    #
    #     $NDK/prebuilt/darwin-x86_64/bin/ndkstack.pyz/ndkstack.py
    #
    # ndk-stack is installed to $NDK/prebuilt/<platform>/bin, so from
    # `android-ndk-r18/prebuilt/linux-x86_64/bin/ndk-stack`...
    # ...get `android-ndk-r18/`:
    path_in_zipped_app = Path(__file__)
    zip_root = path_in_zipped_app.parent
    ndk_bin = zip_root.parent
    ndk_root = ndk_bin.parent.parent.parent
    # ...get `linux-x86_64`:
    ndk_host_tag = ndk_bin.parent.name
    return ndk_root, ndk_bin, ndk_host_tag


def find_llvm_symbolizer(ndk_root: Path, ndk_bin: Path, ndk_host_tag: str) -> Path:
    """Finds the NDK llvm-symbolizer(1) binary.

    Returns: An absolute path to llvm-symbolizer(1).
    """

    llvm_symbolizer = "llvm-symbolizer" + EXE_SUFFIX
    path = (
        ndk_root / "toolchains/llvm/prebuilt" / ndk_host_tag / "bin" / llvm_symbolizer
    )
    if path.exists():
        return path

    # Okay, maybe we're a standalone toolchain? (https://github.com/android-ndk/ndk/issues/931)
    # In that case, llvm-symbolizer and ndk-stack are conveniently in
    # the same directory...
    if (path := ndk_bin / llvm_symbolizer).exists():
        return path
    raise OSError("Unable to find llvm-symbolizer")


def find_readelf(ndk_root: Path, ndk_bin: Path, ndk_host_tag: str) -> Path | None:
    """Finds the NDK readelf(1) binary.

    Returns: An absolute path to readelf(1).
    """

    readelf = "llvm-readelf" + EXE_SUFFIX
    m = re.match("^[^-]+-(.*)", ndk_host_tag)
    if m:
        # Try as if this is not a standalone install.
        path = ndk_root / "toolchains/llvm/prebuilt" / ndk_host_tag / "bin" / readelf
        if path.exists():
            return path

    # Might be a standalone toolchain.
    path = ndk_bin / readelf
    if path.exists():
        return path
    return None


def get_build_id(readelf_path: Path, elf_file: Path) -> bytes | None:
    """Get the GNU build id note from an elf file.

    Returns: The build id found or None if there is no build id or the
             readelf path does not exist.
    """

    try:
        output = subprocess.check_output([str(readelf_path), "-n", str(elf_file)])
        m = re.search(rb"Build ID:\s+([0-9a-f]+)", output)
        if not m:
            return None
        return m.group(1)
    except subprocess.CalledProcessError:
        return None


def get_zip_info_from_offset(
    zip_file: zipfile.ZipFile, offset: int
) -> zipfile.ZipInfo | None:
    """Get the ZipInfo object from a zip file.

    Returns: A ZipInfo object found at the 'offset' into the zip file.
             Returns None if no file can be found at the given 'offset'.
    """
    assert zip_file.filename is not None

    file_size = os.stat(zip_file.filename).st_size
    if offset >= file_size:
        return None

    # The code below requires that the infos are sorted by header_offset,
    # so sort the infos.
    infos = sorted(zip_file.infolist(), key=lambda info: info.header_offset)
    if not infos or offset < infos[0].header_offset:
        return None

    for i in range(1, len(infos)):
        prev_info = infos[i - 1]
        cur_offset = infos[i].header_offset
        if prev_info.header_offset <= offset < cur_offset:
            zip_info = prev_info
            return zip_info
    zip_info = infos[len(infos) - 1]
    if offset < zip_info.header_offset:
        return None
    return zip_info


class FrameInfo:
    """A class to represent the data in a single backtrace frame.

    Attributes:
      num: The string representing the frame number (eg #01).
      pc: The relative program counter for the frame.
      elf_file: The file or map name in which the relative pc resides.
      container_file: The name of the file that contains the elf_file.
                      For example, an entry like GoogleCamera.apk!libsome.so
                      would set container_file to GoogleCamera.apk and
                      set elf_file to libsome.so. Set to None if no ! found.
      offset: The offset into the file at which this library was mapped.
              Set to None if no offset found.
      build_id: The Gnu build id note parsed from the frame information.
                Set to None if no build id found.
      tail: The part of the line after the program counter.
    """

    # See unwindstack::FormatFrame in libunwindstack.
    # We're deliberately very loose because NDK users are likely to be
    # looking at crashes on ancient OS releases.
    # TODO: support asan stacks too?
    #
    # The PC will begin with 0x for some traces. That's not the norm, but we've had a
    # report of traces with that format being provided by the Play console. Presumably
    # either Play is rewriting those (though I can't imagine why they'd be doing that),
    # or some OEM has altered the format of the crash output.
    # See https://github.com/android/ndk/issues/1898.
    _line_re = re.compile(rb".* +(#[0-9]+) +pc (?:0x)?([0-9a-f]+) +(([^ ]+).*)")
    _sanitizer_line_re = re.compile(
        rb".* +(#[0-9]+) +0x[0-9a-f]* +\(([^ ]+)\+0x([0-9a-f]+)\)"
    )
    _lib_re = re.compile(r"([^\!]+)\!(.+)")
    _offset_re = re.compile(rb"\(offset\s+(0x[0-9a-f]+)\)")
    _build_id_re = re.compile(rb"\(BuildId:\s+([0-9a-f]+)\)")

    @classmethod
    def from_line(cls, line: bytes) -> FrameInfo | None:
        m = FrameInfo._line_re.match(line)
        if m:
            num, pc, tail, elf_file = m.group(1, 2, 3, 4)
            # The path in the trace file comes from a POSIX system, so it can
            # contain arbitrary bytes that are not valid UTF-8. If the user is
            # on Windows it's impossible for us to handle those paths. This is
            # an extremely unlikely circumstance. In any case, the fix on the
            # user's side is "don't do that", so just attempt to decode UTF-8
            # and let the exception be thrown if it isn't.
            return cls(num, pc, tail, PurePosixPath(elf_file.decode("utf-8")))
        m = FrameInfo._sanitizer_line_re.match(line)
        if m:
            num, pc, tail, elf_file = m.group(1, 3, 2, 2)
            return cls(
                num, pc, tail, PurePosixPath(elf_file.decode("utf-8")), sanitizer=True
            )
        return None

    def __init__(
        self,
        num: bytes,
        pc: bytes,
        tail: bytes,
        elf_file: PurePosixPath,
        sanitizer: bool = False,
    ) -> None:
        self.num = num
        self.pc = pc
        self.tail = tail
        self.elf_file = elf_file
        self.sanitizer = sanitizer

        if (library_match := FrameInfo._lib_re.match(str(self.elf_file))) is not None:
            self.container_file: PurePosixPath | None = PurePosixPath(
                library_match.group(1)
            )
            self.elf_file = PurePosixPath(library_match.group(2))
            # Sometimes an entry like this will occur:
            #   #01 pc 0000abcd  /system/lib/lib/libc.so!libc.so (offset 0x1000)
            # In this case, no container file should be set.
            if os.path.basename(self.container_file) == os.path.basename(self.elf_file):
                self.elf_file = self.container_file
                self.container_file = None
        else:
            self.container_file = None
        m = FrameInfo._offset_re.search(self.tail)
        if m:
            self.offset: int | None = int(m.group(1), 16)
        else:
            self.offset = None
        m = FrameInfo._build_id_re.search(self.tail)
        if m:
            self.build_id = m.group(1)
        else:
            self.build_id = None

    def verify_elf_file(
        self, build_id_reader: BuildIdReader, elf_file_path: Path, display_elf_path: str
    ) -> bool:
        """Verify if the elf file is valid.

        Returns: True if the elf file exists and build id matches (if it exists).
        """
        return (
            ElfSymbolSource(
                elf_file_path, display_elf_path, build_id_reader
            ).find_providing_elf_file(self)
            is not None
        )

    def get_elf_file(
        self, symbol_dir: Path, build_id_reader: BuildIdReader, tmp_dir: TmpDir
    ) -> Path | None:
        """Get the path to the elf file represented by this frame.

        Returns: The path to the elf file if it is valid, or None if
                 no valid elf file can be found. If the file has to be
                 extracted from an apk, the elf file will be placed in
                 tmp_dir.
        """

        elf_file = self.elf_file.name
        if self.container_file:
            # This matches a file format such as Base.apk!libsomething.so
            # so see if we can find libsomething.so in the symbol directory.
            elf_file_path = symbol_dir / elf_file
            if self.verify_elf_file(build_id_reader, elf_file_path, str(elf_file_path)):
                return elf_file_path

            apk_file_path = symbol_dir / self.container_file.name
            return find_elf_in_apk(
                apk_file_path, self, tmp_dir.get_directory(), build_id_reader
            )
        elif self.elf_file.suffix == ".apk":
            # This matches a stack line such as:
            #   #08 pc 00cbed9c  GoogleCamera.apk (offset 0x6e32000)
            apk_file_path = symbol_dir / elf_file
            with zipfile.ZipFile(apk_file_path) as zip_file:
                assert self.offset is not None
                zip_info = get_zip_info_from_offset(zip_file, self.offset)
                if not zip_info:
                    return None

                # Rewrite the output tail so that it goes from:
                #   GoogleCamera.apk ...
                # To:
                #   GoogleCamera.apk!libsomething.so ...
                index = self.tail.find(elf_file.encode("utf-8"))
                if index != -1:
                    index += len(elf_file)
                    self.tail = (
                        self.tail[0:index]
                        + b"!"
                        + bytes(zip_info.filename, encoding="utf-8")
                        + self.tail[index:]
                    )
                elf_file = os.path.basename(zip_info.filename)
                elf_file_path = symbol_dir / elf_file
                if self.verify_elf_file(
                    build_id_reader, elf_file_path, str(elf_file_path)
                ):
                    return elf_file_path

                elf_file_path = Path(
                    zip_file.extract(zip_info, tmp_dir.get_directory())
                )
                display_elf_path = "%s!%s" % (apk_file_path, elf_file)
                if not self.verify_elf_file(
                    build_id_reader, elf_file_path, display_elf_path
                ):
                    return None
                return elf_file_path
        elf_file_path = symbol_dir / elf_file
        if self.verify_elf_file(build_id_reader, elf_file_path, str(elf_file_path)):
            return elf_file_path
        return None


def get_build_id_reader(ndk_root: Path, ndk_bin: Path, host_tag: str) -> BuildIdReader:
    if (readelf_path := find_readelf(ndk_root, ndk_bin, host_tag)) is not None:
        return Readelf(readelf_path)
    return NullBuildIdReader()


def symbolize_trace(trace_input: BinaryIO, symbol_dir: Path) -> None:
    ndk_root, ndk_bin, host_tag = get_ndk_paths()
    symbolize_cmd = [
        str(find_llvm_symbolizer(ndk_root, ndk_bin, host_tag)),
        "--demangle",
        "--functions=linkage",
        "--inlines",
    ]
    build_id_reader = get_build_id_reader(ndk_root, ndk_bin, host_tag)
    symbolize_proc = None

    try:
        tmp_dir = TmpDir()
        symbolize_proc = subprocess.Popen(
            symbolize_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )
        assert symbolize_proc.stdin is not None
        assert symbolize_proc.stdout is not None
        banner = b"*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***"
        in_crash = False
        saw_frame = False
        for line in trace_input:
            line = line.rstrip()

            if not in_crash:
                if banner in line:
                    in_crash = True
                    saw_frame = False
                    print("********** Crash dump: **********", flush=True)
                continue

            for tag in [b"Build fingerprint:", b"Abort message:"]:
                if tag in line:
                    sys.stdout.buffer.write(line[line.find(tag) :])
                    print(flush=True)
                    continue

            frame_info = FrameInfo.from_line(line)
            if not frame_info:
                if saw_frame:
                    in_crash = False
                    print("Crash dump is completed\n", flush=True)
                continue

            # There can be a gap between sanitizer frames in the abort message
            # and the actual backtrace. Do not end the crash dump until we've
            # seen the actual backtrace.
            if not frame_info.sanitizer:
                saw_frame = True

            try:
                elf_file = frame_info.get_elf_file(symbol_dir, build_id_reader, tmp_dir)
            except IOError:
                elf_file = None

            # Print a slightly different version of the stack trace line.
            # The original format:
            #      #00 pc 0007b350  /lib/bionic/libc.so (__strchr_chk+4)
            # becomes:
            #      #00 0x0007b350 /lib/bionic/libc.so (__strchr_chk+4)
            out_line = b"%s 0x%s %s\n" % (
                frame_info.num,
                frame_info.pc,
                frame_info.tail,
            )
            sys.stdout.buffer.write(out_line)
            indent = (out_line.find(b"(") + 1) * b" "
            if not elf_file:
                continue
            value = b'"%s" 0x%s\n' % (elf_file, frame_info.pc)
            symbolize_proc.stdin.write(value)
            symbolize_proc.stdin.flush()
            while True:
                symbolizer_output = symbolize_proc.stdout.readline().rstrip()
                if not symbolizer_output:
                    break
                # TODO: rewrite file names base on a source path?
                sys.stdout.buffer.write(b"%s%s\n" % (indent, symbolizer_output))
    finally:
        trace_input.close()
        tmp_dir.delete()
        if symbolize_proc:
            assert symbolize_proc.stdin is not None
            assert symbolize_proc.stdout is not None
            symbolize_proc.stdin.close()
            symbolize_proc.stdout.close()
            symbolize_proc.kill()
            symbolize_proc.wait()


def main(argv: list[str] | None = None) -> None:
    """ "Program entry point."""
    parser = argparse.ArgumentParser(
        description="Symbolizes Android crashes.",
        epilog="See <https://developer.android.com/ndk/guides/ndk-stack>.",
    )
    parser.add_argument(
        "-sym",
        "--sym",
        dest="symbol_dir",
        type=Path,
        required=True,  # TODO: default to '.'?
        help="directory containing unstripped .so files",
    )
    parser.add_argument(
        "-i",
        "-dump",
        "--dump",
        dest="input",
        default=sys.stdin.buffer,
        type=argparse.FileType("rb"),
        help="input filename",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.symbol_dir):
        sys.exit("{} does not exist!\n".format(args.symbol_dir))

    symbolize_trace(args.input, args.symbol_dir)


if __name__ == "__main__":
    main()
