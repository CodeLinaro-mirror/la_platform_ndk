#
# Copyright (C) 2017 The Android Open Source Project
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
"""ANSI terminal control."""
from __future__ import absolute_import, print_function

import contextlib
import os
import sys
from typing import Any, Iterator, TextIO

try:
    import termios

    HAVE_TERMIOS = True
except ImportError:
    HAVE_TERMIOS = False


def cursor_up(num_lines: int) -> str:
    """Returns the command to move the cursor up a given number of lines."""
    # \033[0A still goes up one line. Emit nothing.
    if num_lines == 0:
        return ""
    return f"\033[{num_lines}A"


def cursor_down(num_lines: int) -> str:
    """Returns the command to move the cursor down a given number of lines."""
    # \033[0B still goes down one line. Emit nothing.
    if num_lines == 0:
        return ""
    return f"\033[{num_lines}B"


def goto_first_column() -> str:
    """Returns the command to move the cursor to the first column."""
    return "\033[1G"


def clear_line() -> str:
    """Returns the command to clear the current line."""
    return "\033[K"


def font_bold() -> str:
    """Returns the command to set the font to bold."""
    return "\033[1m"


def font_faint() -> str:
    """Returns the command to set the font to faint."""
    return "\033[2m"


def font_reset() -> str:
    """Returns the command to reset the font style."""
    return "\033[0m"


def is_self_in_tty_foreground_group(fd: TextIO) -> bool:
    """Is this process in the foreground process group of a tty identified
    by fd?"""
    return HAVE_TERMIOS and fd.isatty() and os.getpgrp() == os.tcgetpgrp(fd.fileno())


@contextlib.contextmanager
def disable_terminal_echo(fd: TextIO) -> Iterator[None]:
    """Disables terminal echo on the given stream."""
    # If we call tcsetattr from a background process group, it will suspend
    # this process.
    if is_self_in_tty_foreground_group(fd):
        original = termios.tcgetattr(fd)
        termattr = termios.tcgetattr(fd)
        # This is the example from the termios docs, but it doesn't pass type
        # checking...
        termattr[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, termattr)
        try:
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, original)
    else:
        yield


class Console:
    """Manages the state of a console for a stream."""

    def __init__(self, stream: TextIO, smart_console: bool) -> None:
        self.stream = stream
        self.smart_console = smart_console

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Prints the given message to the console.

        Arguments are the same as for the builtin print() function, but file is
        set by default.
        """
        print(*args, file=self.stream, **kwargs)
        self.stream.flush()

    @contextlib.contextmanager
    def cursor_hide_context(self) -> Iterator[None]:
        """A context manager for hiding the cursor on this console."""
        self.hide_cursor()
        try:
            yield
        finally:
            self.show_cursor()

    def clear_lines(self, num_lines: int) -> None:
        """Clears num_lines lines and positions the cursor at the top left."""
        raise NotImplementedError

    def hide_cursor(self) -> None:
        """Hides the cursor."""
        raise NotImplementedError

    def show_cursor(self) -> None:
        """Shows the cursor."""
        raise NotImplementedError


def get_console(stream: TextIO = sys.stdout) -> Console:
    """Returns a Console bound to the given stream."""
    if stream.isatty() and os.name != "nt":
        return AnsiConsole(stream)
    return NonAnsiConsole(stream)


class AnsiConsole(Console):
    """A console that supports ANSI control."""

    GOTO_HOME = "\r"
    CURSOR_UP = "\033[1A"
    CLEAR_LINE = "\033[K"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"

    _size: os.terminal_size

    def __init__(self, stream: TextIO) -> None:
        super().__init__(stream, smart_console=True)
        self._size = os.get_terminal_size()

    def _do(self, cmd: str) -> None:
        """Performs the given command."""
        print(cmd, end="", file=self.stream)
        self.stream.flush()

    def clear_lines(self, num_lines: int) -> None:
        cmds = [self.GOTO_HOME]
        for idx in range(num_lines):
            # For the first line, we're already in place.
            if idx != 0:
                cmds.append(self.CURSOR_UP)
            cmds.append(self.CLEAR_LINE)
        self._do("".join(cmds))

    def hide_cursor(self) -> None:
        self._do(self.HIDE_CURSOR)

    def show_cursor(self) -> None:
        self._do(self.SHOW_CURSOR)

    @property
    def height(self) -> int:
        """The height of the console in characters."""
        return self._size.lines

    @property
    def width(self) -> int:
        """The width of the console in characters."""
        return self._size.columns


class NonAnsiConsole(Console):
    """A console that does not support any ANSI features."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__(stream, smart_console=False)

    def clear_lines(self, _num_lines: int) -> None:
        pass

    def hide_cursor(self) -> None:
        pass

    def show_cursor(self) -> None:
        pass
