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
import textwrap
import unittest
from io import StringIO
from pathlib import Path, PurePosixPath
from typing import Any
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


class FakeBuildIdReader(ndkstack.BuildIdReader):
    def __init__(self, build_id: bytes | None) -> None:
        self._build_id = build_id

    def build_id(self, path: Path) -> bytes | None:
        return self._build_id


class TestElfSymbolSource:
    def test_rejects_mismatched_file_names_with_no_build_id(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"),
            "libapp.so",
            FakeBuildIdReader(None),
        )
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libfake.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_accepts_matching_file_names_with_no_build_id(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"),
            "libapp.so",
            FakeBuildIdReader(None),
        )
        frame = ndkstack.FrameInfo.from_line(b"  #03 pc 00002050  /fake/libapp.so")
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")

    # This is probably the better behavior. If the build IDs match, those debug symbols
    # should be used, even if the libraries were renamed somewhere along the way. This
    # is the existing behavior though, so if we want to make that change it should be
    # done in a follow up.
    @pytest.mark.xfail(reason="not implemented")
    def test_accepts_matching_build_id_with_different_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"),
            "libapp.so",
            FakeBuildIdReader(b"d1d420a58366bf29f1312ec826f16564"),
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")

    def test_rejects_mismatched_build_id_with_same_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libfake.so"),
            "libfake.so",
            FakeBuildIdReader(b"6a0c10d19d5bf39a5a78fa514371dab3"),
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libfake.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) is None

    def test_accepts_matching_build_id_with_same_file_name(self) -> None:
        source = ndkstack.ElfSymbolSource(
            Path("libs/libapp.so"),
            "libapp.so",
            FakeBuildIdReader(b"d1d420a58366bf29f1312ec826f16564"),
        )
        frame = ndkstack.FrameInfo.from_line(
            b"  #03 pc 00002050  /fake/libapp.so (BuildId: d1d420a58366bf29f1312ec826f16564)"
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == Path("libs/libapp.so")


class TestApkSymbolSource:
    def test_rejects_apks_with_no_file_at_offset(self, tmp_path: Path) -> None:
        apk_path = tmp_path / "Test.apk"
        with ZipFile(apk_path, mode="w"):
            # Intentionally empty so no offset matches.
            pass
        source = ndkstack.ApkSymbolSource(apk_path, FakeBuildIdReader(None), tmp_path)
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
            apk_path, FakeBuildIdReader(b"d1d420a58366bf29f1312ec826f16564"), tmp_path
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
            apk_path, FakeBuildIdReader(b"6a0c10d19d5bf39a5a78fa514371dab3"), tmp_path
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
            apk_path, FakeBuildIdReader(b"6a0c10d19d5bf39a5a78fa514371dab3"), tmp_path
        )
        frame = ndkstack.FrameInfo.from_line(
            (
                f"  #03 pc 00002050  /fake/fake.apk (offset 0x{offset:02x}) "
                "(BuildId: 6a0c10d19d5bf39a5a78fa514371dab3)"
            ).encode("utf-8")
        )
        assert frame is not None
        assert source.find_providing_elf_file(frame) == tmp_path / "libtest.so"


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


class GetElfFileTests(unittest.TestCase):
    """Tests of FrameInfo.get_elf_file()."""

    def setUp(self) -> None:
        self.mock_zipfile = mock.MagicMock()
        self.mock_zipfile.extract.return_value = "/fake_tmp/libtest.so"
        self.mock_zipfile.__enter__.return_value = self.mock_zipfile

        self.mock_tmp = mock.MagicMock()
        self.mock_tmp.get_directory.return_value = "/fake_tmp"

    # TODO: Refactor so this can specify a real return type.
    # We can't specify anything more accurate than `Any` here because the real return
    # value is a FrameInfo that's had its verify_elf_file method monkey patched with a
    # mock.
    def create_frame_info(self, tail: bytes) -> Any:
        line = b"  #03 pc 00002050  " + tail
        frame_info = ndkstack.FrameInfo.from_line(line)
        assert frame_info is not None
        # mypy can't (and won't) tolerate this.
        # https://github.com/python/mypy/issues/2427
        frame_info.verify_elf_file = mock.Mock()  # type: ignore
        return frame_info

    def test_file_only(self) -> None:
        frame_info = self.create_frame_info(b"/fake/libfake.so")
        frame_info.verify_elf_file.return_value = True
        self.assertEqual(
            Path("/fake_dir/symbols/libfake.so"),
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp),
        )
        frame_info.verify_elf_file.reset_mock()
        frame_info.verify_elf_file.return_value = False
        self.assertFalse(
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        )
        self.assertEqual(b"/fake/libfake.so", frame_info.tail)

    def test_container_set_elf_in_symbol_dir(self) -> None:
        frame_info = self.create_frame_info(b"/fake/fake.apk!libtest.so")
        frame_info.verify_elf_file.return_value = True
        self.assertEqual(
            Path("/fake_dir/symbols/libtest.so"),
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp),
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so", frame_info.tail)

    def test_container_set_elf_not_in_symbol_dir_apk_does_not_exist(self) -> None:
        frame_info = self.create_frame_info(b"/fake/fake.apk!libtest.so")
        frame_info.verify_elf_file.return_value = False
        with self.assertRaises(IOError):
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        self.assertEqual(b"/fake/fake.apk!libtest.so", frame_info.tail)

    @patch.object(ndkstack, "find_elf_in_apk")
    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_container_set_elf_in_apk(
        self, mock_zipclass: Mock, mock_get_zip_info: Mock, mock_find_elf_in_apk: Mock
    ) -> None:
        mock_zipclass.return_value = self.mock_zipfile
        mock_get_zip_info.return_value.filename = "libtest.so"

        frame_info = self.create_frame_info(
            b"/fake/fake.apk!libtest.so (offset 0x2000)"
        )
        frame_info.verify_elf_file.return_value = False
        # This looks stupid mostly because it is. The important behavior is tested above
        # in TestApkSymbolSource. This just verifies that traces of this pattern will
        # search in APKs.
        mock_find_elf_in_apk.return_value = Path("/fake_tmp/libtest.so")
        self.assertEqual(
            Path("/fake_tmp/libtest.so"),
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp),
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so (offset 0x2000)", frame_info.tail)

    @patch.object(ndkstack, "find_elf_in_apk")
    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_container_set_elf_in_apk_verify_fails(
        self, mock_zipclass: Mock, mock_get_zip_info: Mock, mock_find_elf_in_apk: Mock
    ) -> None:
        mock_zipclass.return_value = self.mock_zipfile
        mock_get_zip_info.return_value.filename = "libtest.so"

        frame_info = self.create_frame_info(
            b"/fake/fake.apk!libtest.so (offset 0x2000)"
        )
        frame_info.verify_elf_file.return_value = False
        mock_find_elf_in_apk.return_value = False
        self.assertFalse(
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so (offset 0x2000)", frame_info.tail)

    def test_in_apk_file_does_not_exist(self) -> None:
        frame_info = self.create_frame_info(b"/fake/fake.apk")
        frame_info.verify_elf_file.return_value = False
        with self.assertRaises(IOError):
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        self.assertEqual(b"/fake/fake.apk", frame_info.tail)

    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_in_apk_elf_not_in_apk(self, _: Mock, mock_get_zip_info: Mock) -> None:
        mock_get_zip_info.return_value = None
        frame_info = self.create_frame_info(b"/fake/fake.apk (offset 0x2000)")
        self.assertFalse(
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        )
        self.assertEqual(b"/fake/fake.apk (offset 0x2000)", frame_info.tail)

    @patch.object(ndkstack, "find_elf_in_apk")
    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_in_apk_elf_in_symbol_dir(
        self, mock_zipclass: Mock, mock_get_zip_info: Mock, mock_find_elf_in_apk: Mock
    ) -> None:
        mock_zipclass.return_value = self.mock_zipfile
        mock_get_zip_info.return_value.filename = "libtest.so"

        def rewrite_tail(
            _path: Path,
            frame_info: ndkstack.FrameInfo,
            _temp_dir: Path,
            _build_id_reader: ndkstack.BuildIdReader,
        ) -> Any:
            frame_info.tail = b"/fake/fake.apk!libtest.so (offset 0x2000)"
            return mock.DEFAULT

        frame_info = self.create_frame_info(b"/fake/fake.apk (offset 0x2000)")
        frame_info.verify_elf_file.return_value = True
        mock_find_elf_in_apk.side_effect = rewrite_tail
        mock_find_elf_in_apk.return_value = Path("/fake_dir/symbols/libtest.so")
        self.assertEqual(
            Path("/fake_dir/symbols/libtest.so"),
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp),
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so (offset 0x2000)", frame_info.tail)

    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_in_apk_elf_in_apk(
        self, mock_zipclass: Mock, mock_get_zip_info: Mock
    ) -> None:
        mock_zipclass.return_value = self.mock_zipfile
        mock_get_zip_info.return_value.filename = "libtest.so"

        frame_info = self.create_frame_info(b"/fake/fake.apk (offset 0x2000)")
        frame_info.verify_elf_file.side_effect = [False, True]
        self.assertEqual(
            Path("/fake_tmp/libtest.so"),
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp),
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so (offset 0x2000)", frame_info.tail)

    @patch.object(ndkstack, "find_elf_in_apk")
    @patch.object(ndkstack, "get_zip_info_from_offset")
    @patch("zipfile.ZipFile")
    def test_in_apk_elf_in_apk_verify_fails(
        self, mock_zipclass: Mock, mock_get_zip_info: Mock, mock_find_elf_in_apk: Mock
    ) -> None:
        mock_zipclass.return_value = self.mock_zipfile
        mock_get_zip_info.return_value.filename = "libtest.so"

        def rewrite_tail(
            _path: Path,
            frame_info: ndkstack.FrameInfo,
            _temp_dir: Path,
            _build_id_reader: ndkstack.BuildIdReader,
        ) -> Any:
            frame_info.tail = b"/fake/fake.apk!libtest.so (offset 0x2000)"
            return mock.DEFAULT

        frame_info = self.create_frame_info(b"/fake/fake.apk (offset 0x2000)")
        frame_info.verify_elf_file.side_effect = False
        mock_find_elf_in_apk.return_value = False
        mock_find_elf_in_apk.side_effect = rewrite_tail
        self.assertFalse(
            frame_info.get_elf_file(Path("/fake_dir/symbols"), None, self.mock_tmp)
        )
        self.assertEqual(b"/fake/fake.apk!libtest.so (offset 0x2000)", frame_info.tail)


if __name__ == "__main__":
    unittest.main()
