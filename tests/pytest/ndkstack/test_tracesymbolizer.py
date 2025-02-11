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
import textwrap
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest

from ndkstack import FrameInfo, Symbolizer, SymbolSource, TraceSymbolizer


class FakeSymbolizer(Symbolizer):
    def __init__(self, trace_mapping: dict[tuple[str, bytes], list[bytes]]) -> None:
        self.trace_mapping = trace_mapping

    def symbolize(self, elf_file: Path, pc: bytes) -> Iterator[bytes]:
        try:
            yield from self.trace_mapping[(str(elf_file), pc)]
        except KeyError:
            yield b"??:0:0"


class FakeSymbolSource(SymbolSource):
    def find_providing_elf_file(self, frame_info: FrameInfo) -> Path | None:
        if frame_info.elf_file is None:
            raise RuntimeError(
                "FakeSymbolSource only accepts frame infos with known ELF files"
            )
        stem = Path(frame_info.elf_file.name)
        if frame_info.abi is not None:
            return Path(frame_info.abi) / stem
        return stem


def test_symbolizes_simple_trace(capsys: pytest.CaptureFixture[str]) -> None:
    trace_symbolizer = TraceSymbolizer(
        FakeSymbolSource(),
        FakeSymbolizer(
            {("libc.so", b"10000000"): [b"abort", b"bionic/libc/abort.cpp:1234"]}
        ),
    )

    trace_symbolizer.symbolize_trace(
        BytesIO(
            textwrap.dedent(
                """\
                not a part of the trace
                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                  #00 pc 10000000  libc.so
                neither is this
                """
            ).encode("utf-8")
        )
    )
    captured = capsys.readouterr()
    assert captured.out == textwrap.dedent(
        """\
        ********** Crash dump: **********
        #00 0x10000000 libc.so
        abort
        bionic/libc/abort.cpp:1234
        Crash dump is completed

        """
    )


def test_considers_abi_context(capsys: pytest.CaptureFixture[str]) -> None:
    trace_symbolizer = TraceSymbolizer(
        FakeSymbolSource(),
        FakeSymbolizer(
            {
                ("x86/libc.so", b"10000000"): [b"abort", b"bionic/libc/abort.cpp:1234"],
                ("x86_64/libc.so", b"20000000"): [
                    b"abort",
                    b"bionic/libc/abort.cpp:1234",
                ],
            }
        ),
    )

    trace_symbolizer.symbolize_trace(
        BytesIO(
            textwrap.dedent(
                """\
                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                ABI: 'x86'
                  #00 pc 10000000  libc.so

                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                ABI: 'x86_64'
                  #00 pc 20000000  libc.so
                """
            ).encode("utf-8")
        )
    )
    captured = capsys.readouterr()
    assert captured.out == textwrap.dedent(
        """\
        ********** Crash dump: **********
        #00 0x10000000 libc.so
        abort
        bionic/libc/abort.cpp:1234
        Crash dump is completed

        ********** Crash dump: **********
        #00 0x20000000 libc.so
        abort
        bionic/libc/abort.cpp:1234
        """
    )


@pytest.mark.xfail()
def test_end_message_shown_if_trace_is_end(capsys: pytest.CaptureFixture[str]) -> None:
    trace_symbolizer = TraceSymbolizer(
        FakeSymbolSource(),
        FakeSymbolizer(
            {("libc.so", b"10000000"): [b"abort", b"bionic/libc/abort.cpp:1234"]}
        ),
    )

    trace_symbolizer.symbolize_trace(
        BytesIO(
            textwrap.dedent(
                """\
                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                  #00 pc 10000000  libc.so
                """
            ).encode("utf-8")
        )
    )
    captured = capsys.readouterr()
    assert captured.out == textwrap.dedent(
        """\
        ********** Crash dump: **********
        #00 0x10000000 libc.so
        abort
        bionic/libc/abort.cpp:1234
        Crash dump is completed

        """
    )


def test_includes_build_fingerprint(capsys: pytest.CaptureFixture[str]) -> None:
    trace_symbolizer = TraceSymbolizer(
        FakeSymbolSource(),
        FakeSymbolizer(
            {("libc.so", b"10000000"): [b"abort", b"bionic/libc/abort.cpp:1234"]}
        ),
    )

    trace_symbolizer.symbolize_trace(
        BytesIO(
            textwrap.dedent(
                """\
                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                Build fingerprint: 'abcdef'
                """
            ).encode("utf-8")
        )
    )
    captured = capsys.readouterr()
    assert captured.out == textwrap.dedent(
        """\
        ********** Crash dump: **********
        Build fingerprint: 'abcdef'
        """
    )


def test_includes_abort_message(capsys: pytest.CaptureFixture[str]) -> None:
    trace_symbolizer = TraceSymbolizer(
        FakeSymbolSource(),
        FakeSymbolizer(
            {("libc.so", b"10000000"): [b"abort", b"bionic/libc/abort.cpp:1234"]}
        ),
    )

    trace_symbolizer.symbolize_trace(
        BytesIO(
            textwrap.dedent(
                """\
                *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
                Abort message: null pointer dereference
                """
            ).encode("utf-8")
        )
    )
    captured = capsys.readouterr()
    assert captured.out == textwrap.dedent(
        """\
        ********** Crash dump: **********
        Abort message: null pointer dereference
        """
    )
