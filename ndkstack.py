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
import functools
import logging
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


def logger() -> logging.Logger:
    """Returns the module-level logger."""
    return logging.getLogger(__name__)


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


class ElfReader(ABC):
    @abstractmethod
    def build_id(self, path: Path) -> bytes | None:
        """Returns the build ID of the given file, or None if none was found."""

    @abstractmethod
    def has_debug_info(self, path: Path) -> bool:
        """Returns True if the path is an ELF file with debug info."""


class Readelf(ElfReader):
    def __init__(self, path: Path) -> None:
        self.path = path

    @functools.lru_cache()
    def build_id(self, path: Path) -> bytes | None:
        return get_build_id(self.path, path)

    @functools.lru_cache()
    def has_debug_info(self, path: Path) -> bool:
        try:
            proc = subprocess.run(
                [self.path, "-SW", path],
                capture_output=True,
                encoding="UTF-8",
                check=True,
            )
            # This may need some tuning. There are a handful of sections that are
            # prefixed with .debug that may have the data we need. This casts an overly
            # broad net, but that's somewhat better than too narrow.
            #
            # .gnu_debugdata is minidebug info, which can also include symbol data.
            return ".debug" in proc.stdout or ".gnu_debugdata" in proc.stdout
        except subprocess.CalledProcessError:
            # Most likely the file isn't an ELF file. We don't really care why it fails
            # though. Just ignore it and move on.
            return False


class NullElfReader(ElfReader):
    def build_id(self, path: Path) -> bytes | None:
        return None

    def has_debug_info(self, path: Path) -> bool:
        # We can't actually know, but the NullElfReader is used in cases where readelf
        # can't be found. In that case, it's better to attempt to get symbols from a
        # file that might have debug info than to reject all files, which would result
        # in never being able to symbolize anything.
        return True


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

    def __init__(self, path: Path, display_path: str, elf_reader: ElfReader) -> None:
        self.path = path
        self.display_path = display_path
        self.elf_reader = elf_reader

    @cached_property
    def build_id(self) -> bytes | None:
        return self.elf_reader.build_id(self.path)

    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        if frame_info.build_id is not None and self.build_id is not None:
            if self.build_id_matches(frame_info.build_id):
                return self.path
            return None
        if not self.elf_reader.has_debug_info(self.path):
            return None
        if frame_info.elf_file is None:
            # The trace frame named a container and an offset but not the file name. We
            # can't find the file until that's been found by parsing the container,
            # which will be done by the container specific SymbolSource.
            return None
        if self.path.name != frame_info.elf_file.name:
            return None
        return self.path

    def build_id_matches(self, build_id: bytes) -> bool:
        """Returns True if the build ID of the ELF file matches the frame info."""
        if self.build_id is None:
            print(f"ERROR: Could not determine build ID for {self.path}", flush=True)
            return False
        if build_id != self.build_id:
            return False
        return True


class ApkSymbolSource(SymbolSource):
    def __init__(self, path: Path, elf_reader: ElfReader, temp_dir: Path) -> None:
        self.path = path
        self.elf_reader = elf_reader
        self.temp_dir = temp_dir

    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        # This matches a file format such as Base.apk!libsomething.so, or possibly
        # Base.apk with an offset but not file name.

        # This should only happen when the trace line is in a file name format (without
        # a container and offset), but the file itself is not in the search directory.
        # In this case we won't be able to find the symbols even if they are present in
        # an APK in the search directory, because checking build IDs on every library in
        # each APK in the search directory could be prohibitively expensive (the user
        # could have given their whole AGP build directory as a search path). We may
        # still find symbols in that situation as long as a previous frame was in the
        # container/offset format and caused a file with a build ID to be extracted,
        # because then we will find the result in the build ID cache.
        if frame_info.offset is None:
            return None

        with zipfile.ZipFile(self.path) as zip_file:
            zip_info = get_zip_info_from_offset(zip_file, frame_info.offset)
            if not zip_info:
                return None
            elf_file_path = Path(zip_file.extract(zip_info, self.temp_dir))
            if frame_info.elf_file is None:
                # This shouldn't ever happen outside tests. We try to fill this data in
                # before ever scanning the directory because we want to prefer non-APK
                # matches, but the redundant check here allows us to test the nameless
                # trace handling in ApkSymbolSource without needing to rely on
                # DirectorySymbolSource as well.
                #
                # TODO: Fixup names during FrameInfo creation.
                # Moving the name fixups outside the symbol search entirely would make
                # the code responsible for it much less messy, but requires some
                # additional plumbing.
                frame_info.fixup_unknown_elf_file(elf_file_path)
            assert frame_info.elf_file is not None
            display_elf_file = f"{self.path}!{frame_info.elf_file.name}"
            source = ElfSymbolSource(elf_file_path, display_elf_file, self.elf_reader)
            if (provider := source.find_providing_elf_file(frame_info)) is not None:
                return provider
            return None


class DirectorySymbolSource(SymbolSource):
    def __init__(self, path: Path, elf_reader: ElfReader, temp_dir: Path) -> None:
        self.path = path
        self.elf_reader = elf_reader
        self.temp_dir = temp_dir
        self._cache_by_build_id: dict[bytes, Path] = {}
        self._cache_by_path: dict[PurePosixPath, Path] = {}
        self._cache_by_container_offset: dict[tuple[PurePosixPath, int], Path] = {}

    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        if (provider := self._find_cached(frame_info)) is not None:
            return provider

        # For lines like "#00 pc 0000e4fc  test.apk (offset 0x1000)", we need to fill
        # out the missing file name before we start the search. This is because we want
        # to match non-APK sources first for performance reasons (we don't have to
        # extract the APK that way), but to do that we need to know the name of the ELF
        # file first.
        if frame_info.container_file is not None and frame_info.elf_file is None:
            self._fixup_elf_file_name(frame_info)

        container_sources: list[Path] = []
        # TODO: Make recursive?
        # Making this recursive will require more careful handling of multiple matches.
        # If the user gives their whole AGP build directory as the search path, the
        # directory will have both stripped and unstripped libraries, and we'll need to
        # avoid matching the stripped library when an unstripped one is available.
        # TODO: Try matching file names first to speed up search.
        for path in self.path.iterdir():
            if not path.is_file():
                continue

            if path.suffix == ".apk":
                # Search these after we've exhausted the bare files. Searching APKs
                # requires extracting the libraries from the APK, and if the file is
                # already extracted, we prefer that source rather than doing the work to
                # extract the library from the APK.
                container_sources.append(path)
                continue

            provider = ElfSymbolSource(
                path, str(path), self.elf_reader
            ).find_providing_elf_file(frame_info)
            if provider is not None:
                self._cache_result(frame_info, provider)
                return provider

        for path in container_sources:
            provider = ApkSymbolSource(
                path, self.elf_reader, self.temp_dir
            ).find_providing_elf_file(frame_info)
            if provider is not None:
                self._cache_result(frame_info, provider)
                return provider
            return None
        return None

    def _find_cached(self, frame_info: FrameInfo) -> Path | None:
        if frame_info.build_id is not None:
            return self._cache_by_build_id.get(frame_info.build_id)
        if frame_info.elf_file is not None:
            # There's no need to fall through to container/offset cache searching if the
            # frame has a known file name. If we previously found a cache/offset match
            # and entered it into the cache, its file name will have also been entered.
            return self._cache_by_path.get(frame_info.elf_file)
        if frame_info.container_file is not None and frame_info.offset is not None:
            return self._cache_by_container_offset.get(
                (frame_info.container_file, frame_info.offset)
            )
        return None

    def _cache_result(self, frame_info: FrameInfo, path: Path) -> None:
        # This can be absent at the beginning of a search in the case where a trace line
        # has a container name and an offset, but will be filled in if we find the
        # result in an APK. If we find a build ID match in a file without having to
        # search for the file in an APK, however, the name won't have been populated.
        if frame_info.elf_file is not None:
            self._cache_by_path[frame_info.elf_file] = path
        if frame_info.container_file is not None and frame_info.offset is not None:
            self._cache_by_container_offset[
                (frame_info.container_file, frame_info.offset)
            ] = path
        if frame_info.build_id is not None:
            self._cache_by_build_id[frame_info.build_id] = path

    def _fixup_elf_file_name(self, frame_info: FrameInfo) -> None:
        if frame_info.offset is None:
            logger().warning(
                "Frame has no file name or container offset, cannot find symbols: %s",
                frame_info.raw.decode("utf-8"),
            )
            return

        for path in self.path.glob("*.apk"):
            if not path.is_file():
                continue

            with zipfile.ZipFile(path) as zip_file:
                zip_info = get_zip_info_from_offset(zip_file, frame_info.offset)
                if not zip_info:
                    continue
                frame_info.fixup_unknown_elf_file(Path(zip_info.filename))
                return


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
        proc = subprocess.run(
            [str(readelf_path), "-n", str(elf_file)], capture_output=True, check=True
        )
        m = re.search(rb"Build ID:\s+([0-9a-f]+)", proc.stdout)
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
            return cls(line, num, pc, tail, PurePosixPath(elf_file.decode("utf-8")))
        m = FrameInfo._sanitizer_line_re.match(line)
        if m:
            num, pc, tail, elf_file = m.group(1, 3, 2, 2)
            return cls(
                line,
                num,
                pc,
                tail,
                PurePosixPath(elf_file.decode("utf-8")),
                sanitizer=True,
            )
        return None

    def __init__(
        self,
        raw: bytes,
        num: bytes,
        pc: bytes,
        tail: bytes,
        elf_file: PurePosixPath,
        sanitizer: bool = False,
    ) -> None:
        self.raw = raw
        self.num = num
        self.pc = pc
        self.tail = tail
        self.elf_file: PurePosixPath | None = elf_file
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
        elif self.elf_file.suffix == ".apk":
            # Some traces have containers but no ELF file name. When this happens the
            # APK will be wrongly parsed as the ELF file and we won't have a container.
            # Rewrite those so that they identify the container correctly with an absent
            # ELF file rather than having to deal with that quirk elsewhere.
            self.container_file = self.elf_file
            self.elf_file = None
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

    def fixup_unknown_elf_file(self, elf_path: Path) -> None:
        """Updates the ELF file of the trace and rewrites the tail with the new path.

        This cannot be done during parsing because some traces contain an APK name but
        no ELF file. When this happens there's an offset which allows us to find the
        file in the APK, but we can't do that until we've found and read the APK, which
        happens later.

        When this happens we also rewrite the tail so the log we print is more helpful
        to the user.
        """
        assert self.container_file is not None
        container_name = self.container_file.name
        self.elf_file = PurePosixPath(elf_path.name)
        # Rewrite the output tail so that it goes from:
        #   GoogleCamera.apk ...
        # To:
        #   GoogleCamera.apk!libsomething.so ...
        index = self.tail.find(container_name.encode("utf-8"))
        if index != -1:
            index += len(container_name)
            self.tail = (
                self.tail[0:index]
                + b"!"
                + bytes(elf_path.name, encoding="utf-8")
                + self.tail[index:]
            )


def get_elf_reader(ndk_root: Path, ndk_bin: Path, host_tag: str) -> ElfReader:
    if (readelf_path := find_readelf(ndk_root, ndk_bin, host_tag)) is not None:
        return Readelf(readelf_path)
    return NullElfReader()


def symbolize_trace(trace_input: BinaryIO, symbol_dir: Path) -> None:
    ndk_root, ndk_bin, host_tag = get_ndk_paths()
    symbolize_cmd = [
        str(find_llvm_symbolizer(ndk_root, ndk_bin, host_tag)),
        "--demangle",
        "--functions=linkage",
        "--inlines",
    ]
    elf_reader = get_elf_reader(ndk_root, ndk_bin, host_tag)
    symbolize_proc = None

    try:
        tmp_dir = TmpDir()
        symbol_source = DirectorySymbolSource(
            symbol_dir, elf_reader, Path(tmp_dir.get_directory())
        )
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
                elf_file = symbol_source.find_providing_elf_file(frame_info)
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
