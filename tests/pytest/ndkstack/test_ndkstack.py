#!/usr/bin/env python3
#
# Copyright (C) 2019 The Android Open Source Project
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
"""Unittests for ndk-stack.py"""
import unittest
from pathlib import Path, PurePosixPath
from unittest import mock
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest

import ndkstack


class TestFindLlvmSymbolizer:
    def test_find_in_prebuilt(self, tmp_path: Path) -> None:
        ndk_path = tmp_path / "ndk"
        symbolizer_path = (
            ndk_path / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-symbolizer"
        )
        symbolizer_path = symbolizer_path.with_suffix(ndkstack.EXE_SUFFIX)
        symbolizer_path.parent.mkdir(parents=True)
        symbolizer_path.touch()
        assert (
            ndkstack.find_llvm_symbolizer(ndk_path, ndk_path / "bin", "linux-x86_64")
            == symbolizer_path
        )

    def test_find_in_standalone_toolchain(self, tmp_path: Path) -> None:
        ndk_path = tmp_path / "ndk"
        symbolizer_path = ndk_path / "bin/llvm-symbolizer"
        symbolizer_path = symbolizer_path.with_suffix(ndkstack.EXE_SUFFIX)
        symbolizer_path.parent.mkdir(parents=True)
        symbolizer_path.touch()
        assert (
            ndkstack.find_llvm_symbolizer(ndk_path, ndk_path / "bin", "linux-x86_64")
            == symbolizer_path
        )

    def test_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(OSError, match="Unable to find llvm-symbolizer"):
            ndkstack.find_llvm_symbolizer(tmp_path, tmp_path / "bin", "linux-x86_64")


class TestFindReadelf:
    def test_find_in_prebuilt(self, tmp_path: Path) -> None:
        ndk_path = tmp_path / "ndk"
        readelf_path = (
            ndk_path / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
        )
        readelf_path = readelf_path.with_suffix(ndkstack.EXE_SUFFIX)
        readelf_path.parent.mkdir(parents=True)
        readelf_path.touch()
        assert (
            ndkstack.find_readelf(ndk_path, ndk_path / "bin", "linux-x86_64")
            == readelf_path
        )

    def test_find_in_standalone_toolchain(self, tmp_path: Path) -> None:
        ndk_path = tmp_path / "ndk"
        readelf_path = ndk_path / "bin/llvm-readelf"
        readelf_path = readelf_path.with_suffix(ndkstack.EXE_SUFFIX)
        readelf_path.parent.mkdir(parents=True)
        readelf_path.touch()
        assert (
            ndkstack.find_readelf(ndk_path, ndk_path / "bin", "linux-x86_64")
            == readelf_path
        )

    def test_not_found(self, tmp_path: Path) -> None:
        assert ndkstack.find_readelf(tmp_path, tmp_path / "bin", "linux-x86_64") is None


class FrameTests(unittest.TestCase):
    """Test parsing of backtrace lines."""

    def test_line_with_map_name(self) -> None:
        line = b"  #14 pc 00001000  /fake/libfake.so"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#14", frame_info.num)
        self.assertEqual(b"00001000", frame_info.pc)
        self.assertEqual(b"/fake/libfake.so", frame_info.tail)
        self.assertEqual(PurePosixPath("/fake/libfake.so"), frame_info.elf_file)
        self.assertFalse(frame_info.offset)
        self.assertFalse(frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_with_function(self) -> None:
        line = b"  #08 pc 00001040  /fake/libfake.so (func())"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#08", frame_info.num)
        self.assertEqual(b"00001040", frame_info.pc)
        self.assertEqual(b"/fake/libfake.so (func())", frame_info.tail)
        self.assertEqual(PurePosixPath("/fake/libfake.so"), frame_info.elf_file)
        self.assertFalse(frame_info.offset)
        self.assertFalse(frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_with_offset(self) -> None:
        line = b"  #04 pc 00002050  /fake/libfake.so (offset 0x2000)"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#04", frame_info.num)
        self.assertEqual(b"00002050", frame_info.pc)
        self.assertEqual(b"/fake/libfake.so (offset 0x2000)", frame_info.tail)
        self.assertEqual(PurePosixPath("/fake/libfake.so"), frame_info.elf_file)
        self.assertEqual(0x2000, frame_info.offset)
        self.assertFalse(frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_with_build_id(self) -> None:
        line = b"  #03 pc 00002050  /fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#03", frame_info.num)
        self.assertEqual(b"00002050", frame_info.pc)
        self.assertEqual(
            b"/fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)",
            frame_info.tail,
        )
        self.assertEqual(PurePosixPath("/fake/libfake.so"), frame_info.elf_file)
        self.assertFalse(frame_info.offset)
        self.assertFalse(frame_info.container_file)
        self.assertEqual(b"d1d420a58366bf29f1312ec826f16564", frame_info.build_id)

    def test_line_with_container_file(self) -> None:
        line = b"  #10 pc 00003050  /fake/fake.apk!libc.so"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#10", frame_info.num)
        self.assertEqual(b"00003050", frame_info.pc)
        self.assertEqual(b"/fake/fake.apk!libc.so", frame_info.tail)
        self.assertEqual(PurePosixPath("libc.so"), frame_info.elf_file)
        self.assertFalse(frame_info.offset)
        self.assertEqual(PurePosixPath("/fake/fake.apk"), frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_with_container_file_and_no_library(self) -> None:
        line = b"  #10 pc 00003050  /fake/fake.apk (offset 0x2000)"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#10", frame_info.num)
        self.assertEqual(b"00003050", frame_info.pc)
        self.assertEqual(b"/fake/fake.apk (offset 0x2000)", frame_info.tail)
        self.assertIsNone(frame_info.elf_file)
        self.assertEqual(frame_info.offset, 0x2000)
        self.assertEqual(PurePosixPath("/fake/fake.apk"), frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_with_container_and_elf_equal(self) -> None:
        line = b"  #12 pc 00004050  /fake/libc.so!lib/libc.so"
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#12", frame_info.num)
        self.assertEqual(b"00004050", frame_info.pc)
        self.assertEqual(b"/fake/libc.so!lib/libc.so", frame_info.tail)
        self.assertEqual(PurePosixPath("/fake/libc.so"), frame_info.elf_file)
        self.assertFalse(frame_info.offset)
        self.assertFalse(frame_info.container_file)
        self.assertFalse(frame_info.build_id)

    def test_line_everything(self) -> None:
        line = (
            b"  #07 pc 00823fc  /fake/fake.apk!libc.so (__start_thread+64) "
            b"(offset 0x1000) (BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
        )
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        self.assertEqual(b"#07", frame_info.num)
        self.assertEqual(b"00823fc", frame_info.pc)
        self.assertEqual(
            b"/fake/fake.apk!libc.so (__start_thread+64) "
            b"(offset 0x1000) (BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)",
            frame_info.tail,
        )
        self.assertEqual(PurePosixPath("libc.so"), frame_info.elf_file)
        self.assertEqual(0x1000, frame_info.offset)
        self.assertEqual(PurePosixPath("/fake/fake.apk"), frame_info.container_file)
        self.assertEqual(b"6a0c10d19d5bf39a5a78fa514371dab3", frame_info.build_id)

    def test_0x_prefixed_address(self) -> None:
        """Tests that addresses beginning with 0x are parsed correctly."""
        frame_info = ndkstack.FrameInfo.from_line(
            b"  #00  pc 0x000000000006263c  "
            b"/apex/com.android.runtime/lib/bionic/libc.so (abort+172)"
        )
        assert frame_info is not None
        assert frame_info.pc == b"000000000006263c"


class FakeElfReader(ndkstack.ElfReader):
    def __init__(
        self, build_id: bytes | None = None, has_debug_info: bool = True
    ) -> None:
        self._build_id = build_id
        self._has_debug_info = has_debug_info

    def build_id(self, path: Path) -> bytes | None:
        return self._build_id

    def has_debug_info(self, path: Path) -> bool:
        return self._has_debug_info


class PathSuffixFakeBuildIdReader(ndkstack.ElfReader):
    def __init__(
        self, build_id_path_map: dict[Path, bytes | None], suffix_components: int
    ) -> None:
        self.build_id_path_map = build_id_path_map
        self.suffix_components = suffix_components

    def build_id(self, path: Path) -> bytes | None:
        # Construct a new Path using only the final suffix_components parts of the path.
        # This will turn a/b/c/d into c/d if suffix_components is 2.
        suffix = Path(*path.parts[-self.suffix_components :])
        return self.build_id_path_map.get(suffix)

    def has_debug_info(self, path: Path) -> bool:
        return True


class TestElfSymbolSource:
    def test_rejects_mismatched_file_names_with_no_build_id(self) -> None:
        source = ndkstack.ElfSymbolSource(Path("libs/libapp.so"), FakeElfReader())
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libfake.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_accepts_matching_file_names_with_no_build_id(self) -> None:
        source = ndkstack.ElfSymbolSource(Path("libs/libapp.so"), FakeElfReader())
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libapp.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")

    def test_accepts_matching_build_id_with_different_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"), FakeElfReader(b"d1d420a58366bf29f1312ec826f16564")
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")

    def test_rejects_mismatched_build_id_with_same_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libfake.so"), FakeElfReader(b"6a0c10d19d5bf39a5a78fa514371dab3")
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_accepts_matching_build_id_with_same_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"), FakeElfReader(b"d1d420a58366bf29f1312ec826f16564")
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libapp.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")

    def test_rejects_file_without_debug_info(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libfake.so"), FakeElfReader(has_debug_info=False)
        )
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libfake.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_matches_alternate_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libfake.so.dbg"), FakeElfReader(), name_for_match="libfake.so"
        )
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libfake.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libfake.so.dbg")


class TestApkSymbolSource:
    def test_rejects_apks_with_no_file_at_offset(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w"):
            # Intentionally empty so no offset matches.
            pass
        source = ndkstack.ApkSymbolSource(apk_path, FakeElfReader(), tmp_path)
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/fake.apk!libtest.so (offset 0x2000)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_rejects_mismatched_build_ids(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libtest.so", "")
            offset = zip_file.getinfo("libtest.so").header_offset
        source = ndkstack.ApkSymbolSource(
            apk_path,
            FakeElfReader(b"d1d420a58366bf29f1312ec826f16564"),
            tmp_path,
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk!libtest.so (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_finds_file_in_apk(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libtest.so", "")
            offset = zip_file.getinfo("libtest.so").header_offset
        source = ndkstack.ApkSymbolSource(
            apk_path,
            FakeElfReader(b"6a0c10d19d5bf39a5a78fa514371dab3"),
            tmp_path,
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk!libtest.so (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libtest.so"

    def test_finds_file_in_container_only_frame(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libtest.so", "")
            offset = zip_file.getinfo("libtest.so").header_offset
        source = ndkstack.ApkSymbolSource(
            apk_path,
            FakeElfReader(b"6a0c10d19d5bf39a5a78fa514371dab3"),
            tmp_path,
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libtest.so"


class TestPlayDebugZipSymbolSource:
    def test_finds_matched_build_id(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "native-debug-symbols.zip"
        with ZipFile(zip_path, mode="w") as zip_file:
            zip_file.writestr("arm64-v8a/libapp.so.dbg", "arm64-v8a/libapp.so")
            zip_file.writestr("armeabi-v7a/libapp.so.dbg", "armeabi-v7a/libapp.so")
            zip_file.writestr("x86/libapp.so.dbg", "x86/libapp.so")
            zip_file.writestr("x86_64/libapp.so.dbg", "x86_64/libapp.so")

        source = ndkstack.PlayDebugZipSymbolSource(
            zip_path,
            PathSuffixFakeBuildIdReader(
                {
                    Path("arm64-v8a/libapp.so.dbg"): b"0123",
                    Path("armeabi-v7a/libapp.so.dbg"): b"4567",
                    Path("x86/libapp.so.dbg"): b"89ab",
                    Path("x86_64/libapp.so.dbg"): b"cdef",
                },
                suffix_components=2,
            ),
            tmp_path,
        )

        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  libtest.so (BuildId: 4567)"
        )
        assert frame is not None
        provider = source.find_providing_elf_file(frame)
        assert provider is not None
        assert provider.read_text() == "armeabi-v7a/libapp.so"

    def test_rejects_unmatch_build_id(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "native-debug-symbols.zip"
        with ZipFile(zip_path, mode="w") as zip_file:
            zip_file.writestr("arm64-v8a/libapp.so.dbg", "arm64-v8a/libapp.so")
            zip_file.writestr("armeabi-v7a/libapp.so.dbg", "armeabi-v7a/libapp.so")
            zip_file.writestr("x86/libapp.so.dbg", "x86/libapp.so")
            zip_file.writestr("x86_64/libapp.so.dbg", "x86_64/libapp.so")

        source = ndkstack.PlayDebugZipSymbolSource(
            zip_path,
            PathSuffixFakeBuildIdReader(
                {
                    Path("arm64-v8a/libapp.so.dbg"): b"0123",
                    Path("armeabi-v7a/libapp.so.dbg"): b"4567",
                    Path("x86/libapp.so.dbg"): b"89ab",
                    Path("x86_64/libapp.so.dbg"): b"cdef",
                },
                suffix_components=2,
            ),
            tmp_path,
        )

        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  libtest.so (BuildId: 4827)"
        )
        assert frame is not None
        provider = source.find_providing_elf_file(frame)
        assert provider is None

    def test_finds_correct_abi_without_build_id(self, tmp_path: Path) -> None:
        zip_path = tmp_path / "native-debug-symbols.zip"
        with ZipFile(zip_path, mode="w") as zip_file:
            zip_file.writestr("arm64-v8a/libapp.so.dbg", "arm64-v8a/libapp.so")
            zip_file.writestr("armeabi-v7a/libapp.so.dbg", "armeabi-v7a/libapp.so")
            zip_file.writestr("x86/libapp.so.dbg", "x86/libapp.so")
            zip_file.writestr("x86_64/libapp.so.dbg", "x86_64/libapp.so")

        source = ndkstack.PlayDebugZipSymbolSource(zip_path, FakeElfReader(), tmp_path)
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  libapp.so", abi="x86")
        assert frame is not None
        provider = source.find_providing_elf_file(frame)
        assert provider is not None
        assert provider.read_text() == "x86/libapp.so"


class TestDirectorySymbolSource:
    def test_finds_file_in_directory(self, tmp_path: Path) -> None:
        (tmp_path / "libapp.so").touch()
        source = ndkstack.DirectorySymbolSource(
            tmp_path, FakeElfReader(), tmp_path / "tmp"
        )
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libapp.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libapp.so"

    def test_finds_file_in_apk(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libapp.so", "")
            offset = zip_file.getinfo("libapp.so").header_offset

        source = ndkstack.DirectorySymbolSource(
            tmp_path, FakeElfReader(), tmp_path / "tmp"
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "tmp/libapp.so"

    def test_reuses_extracted_apk_source(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libapp.so", "")
            offset = zip_file.getinfo("libapp.so").header_offset

        source = ndkstack.DirectorySymbolSource(
            tmp_path, FakeElfReader(), tmp_path / "tmp"
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "tmp/libapp.so"
        first_mtime = (tmp_path / "tmp/libapp.so").stat().st_mtime

        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "tmp/libapp.so"

        assert (tmp_path / "tmp/libapp.so").stat().st_mtime == first_mtime

    def test_prefers_non_container_source(self, tmp_path: Path) -> None:
        # This test is not (and cannot) be completely reliable. The implementation uses
        # Path.iterdir() internally, whose iteration order is not documented, but is
        # almost certainly directory order, which varies by file system. If this test
        # fails, there is a bug in the implementation, but it may incorrectly pass.
        #
        # Try to get the APK to show up first by making sure it's both the first file
        # added to the directory, and alphabetically first. It's not a guarantee, but
        # it's correct on at least some systems.
        apk_path = tmp_path / "0Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libapp.so", "")
            offset = zip_file.getinfo("libapp.so").header_offset
        (tmp_path / "libapp.so").touch()

        source = ndkstack.DirectorySymbolSource(
            tmp_path, FakeElfReader(), tmp_path / "tmp"
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/0Test.apk!libapp.so (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libapp.so"

    def test_finds_build_id_match_without_apk(self, tmp_path: Path) -> None:
        (tmp_path / "libapp.so").touch()
        source = ndkstack.DirectorySymbolSource(
            tmp_path,
            FakeElfReader(b"6a0c10d19d5bf39a5a78fa514371dab3"),
            tmp_path / "tmp",
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/fake.apk (offset 0x0) "
            b"(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libapp.so"

    def test_finds_named_file_from_previously_extracted_apk(
        self, tmp_path: Path
    ) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w") as zip_file:
            zip_file.writestr("libapp.so", "")
            offset = zip_file.getinfo("libapp.so").header_offset

        source = ndkstack.DirectorySymbolSource(
            tmp_path,
            FakeElfReader(b"6a0c10d19d5bf39a5a78fa514371dab3"),
            tmp_path / "tmp",
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "tmp/libapp.so"

        # This file doesn't exist in the symbol directory, but does exist in the temp
        # dir because it was found from the previous APK trace.
        #
        # We do **not** find sources if the file was not previously found. Finding a
        # matching ELF file by only name/build ID when the file is not present in an
        # unextracted form on disk would require extracting every zip/APK found in the
        # directory, which would be probitively costly if the user passed, say, the AGP
        # build directory as their search directory.
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libapp.so "
            b"(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "tmp/libapp.so"


class GetZipInfoFromOffsetTests(unittest.TestCase):
    """Tests of get_zip_info_from_offset()."""

    def setUp(self) -> None:
        self.mock_zip = mock.MagicMock()
        self.mock_zip.filename = "/fake/zip.apk"
        self.mock_zip.infolist.return_value = []

    def test_file_does_not_exist(self) -> None:
        with self.assertRaises(IOError):
            _ = ndkstack.get_zip_info_from_offset(self.mock_zip, 0x1000)

    @patch("os.stat")
    def test_offset_ge_file_size(self, mock_stat: Mock) -> None:
        mock_stat.return_value.st_size = 0x1000
        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x1000))
        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x1100))

    @patch("os.stat")
    def test_empty_infolist(self, mock_stat: Mock) -> None:
        mock_stat.return_value.st_size = 0x1000
        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x900))

    @patch("os.stat")
    def test_zip_info_single_element(self, mock_stat: Mock) -> None:
        mock_stat.return_value.st_size = 0x2000

        mock_zip_info = mock.MagicMock()
        mock_zip_info.header_offset = 0x100
        self.mock_zip.infolist.return_value = [mock_zip_info]

        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x50))

        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x2000))

        zip_info = ndkstack.get_zip_info_from_offset(self.mock_zip, 0x200)
        assert zip_info is not None
        self.assertEqual(0x100, zip_info.header_offset)

    @patch("os.stat")
    def test_zip_info_checks(self, mock_stat: Mock) -> None:
        mock_stat.return_value.st_size = 0x2000

        mock_zip_info1 = mock.MagicMock()
        mock_zip_info1.header_offset = 0x100
        mock_zip_info2 = mock.MagicMock()
        mock_zip_info2.header_offset = 0x1000
        self.mock_zip.infolist.return_value = [mock_zip_info1, mock_zip_info2]

        self.assertFalse(ndkstack.get_zip_info_from_offset(self.mock_zip, 0x50))

        zip_info = ndkstack.get_zip_info_from_offset(self.mock_zip, 0x200)
        assert zip_info is not None
        self.assertEqual(0x100, zip_info.header_offset)

        zip_info = ndkstack.get_zip_info_from_offset(self.mock_zip, 0x100)
        assert zip_info is not None
        self.assertEqual(0x100, zip_info.header_offset)

        zip_info = ndkstack.get_zip_info_from_offset(self.mock_zip, 0x1000)
        assert zip_info is not None
        self.assertEqual(0x1000, zip_info.header_offset)


class TestParseAbi:
    def test_parse_abi_from_line(self) -> None:
        assert (
            ndkstack.parse_abi_from_line(
                b"12-12 15:10:14.473  8156  8156 F DEBUG   : ABI: 'arm'"
            )
            == "armeabi-v7a"
        )
        assert (
            ndkstack.parse_abi_from_line(
                b"12-12 15:10:14.473  8156  8156 F DEBUG   : ABI: 'arm64'"
            )
            == "arm64-v8a"
        )
        assert (
            ndkstack.parse_abi_from_line(
                b"12-12 15:10:14.473  8156  8156 F DEBUG   : ABI: 'x86'"
            )
            == "x86"
        )
        assert (
            ndkstack.parse_abi_from_line(
                b"12-12 15:10:14.473  8156  8156 F DEBUG   : ABI: 'x86_64'"
            )
            == "x86_64"
        )


if __name__ == "__main__":
    unittest.main()
