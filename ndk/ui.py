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
"""UI classes for build output."""
from __future__ import absolute_import, division, print_function

import os
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Iterable, List, Optional, Tuple

import ndk.ansi
from ndk.workqueue import AnyWorkQueue


class UiRenderer:
    """Renders a UI to a console."""

    def __init__(self, console: ndk.ansi.Console) -> None:
        self.console = console

    def clear_last_render(self) -> None:
        """Clears the screen of the previous render."""
        raise NotImplementedError

    def render(self, lines: List[str]) -> None:
        """Renders the given UI, described as a list of console lines."""
        raise NotImplementedError


class AnsiUiRenderer(UiRenderer):
    """Renders a UI to an ANSI console."""

    # Number of seconds to delay between each draw command when debugging.
    debug_draw_delay = 0.1

    def __init__(self, console: ndk.ansi.Console, debug_draw: bool = False) -> None:
        super().__init__(console)
        self.last_rendered_lines: List[str] = []
        self.debug_draw = debug_draw

    def changed_lines(self, new_lines: List[str]) -> Iterable[Tuple[int, str]]:
        """Returns a list of changed lines.

        Returns: A list of tuples describing the changed lines in the format
            (index, contents of new line).
        """
        assert len(new_lines) == len(self.last_rendered_lines)
        old_lines = self.last_rendered_lines
        for idx, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
            if old_line != new_line:
                yield idx, new_line

    def clear_last_render(self) -> None:
        self.console.clear_lines(len(self.last_rendered_lines))
        self.last_rendered_lines = []

    def draw(self, commands: List[str]) -> None:
        """Sends the given UI commands to the console.

        If debug_draw is set, each command will be sent with a delay to make
        the changes slowly enough to be visibly debugged.
        """
        if self.debug_draw:
            for cmd in commands:
                self.console.print(cmd, end="")
                time.sleep(self.debug_draw_delay)
        else:
            self.console.print("".join(commands), end="")

    def render(self, lines: List[str]) -> None:
        if not self.last_rendered_lines:
            self.console.print(os.linesep.join(lines), end="")
        elif len(lines) != len(self.last_rendered_lines):
            self.clear_last_render()
            self.render(lines)
        else:
            redraw_commands = []
            last_idx = 0
            for idx, new_line in self.changed_lines(lines):
                redraw_commands.append(ndk.ansi.cursor_down(idx - last_idx))
                redraw_commands.append(ndk.ansi.goto_first_column())
                redraw_commands.append(ndk.ansi.clear_line())
                redraw_commands.append(new_line)
                last_idx = idx
            if redraw_commands:
                total_lines = len(self.last_rendered_lines)
                goto_top = ndk.ansi.cursor_up(total_lines - 1)
                goto_bottom = ndk.ansi.cursor_down(total_lines - last_idx - 1)

                self.draw([goto_top] + redraw_commands + [goto_bottom])

        self.last_rendered_lines = lines


class NonAnsiUiRenderer(UiRenderer):
    """Renders a UI to a non-ANSI console."""

    def __init__(self, console: ndk.ansi.Console, redraw_rate: int = 30) -> None:
        super().__init__(console)
        self.redraw_rate = redraw_rate
        self.last_draw: Optional[float] = None

    def clear_last_render(self) -> None:
        pass

    def ready_for_draw(self) -> bool:
        """Returns True if the redraw delay has elapsed."""
        if self.last_draw is None:
            return True

        current_time = time.time()
        if current_time - self.last_draw >= self.redraw_rate:
            return True

        return False

    def render(self, lines: List[str]) -> None:
        if not self.ready_for_draw():
            return

        self.console.print(os.linesep.join(lines))
        sys.stdout.flush()
        self.last_draw = time.time()


class Ui:
    """Console UI base class."""

    def __init__(self, ui_renderer: UiRenderer) -> None:
        self.ui_renderer = ui_renderer

    def get_ui_lines(self) -> List[str]:
        """Returns a list of lines describing the current UI state."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clears the UI."""
        self.ui_renderer.clear_last_render()

    def draw(self) -> None:
        """Draws the UI."""
        self.ui_renderer.render(self.get_ui_lines())


class BuildProgressUi(Ui):
    """A UI for displaying build status."""

    def __init__(self, ui_renderer: UiRenderer, workqueue: AnyWorkQueue) -> None:
        super().__init__(ui_renderer)
        self.workqueue = workqueue

    def get_ui_lines(self) -> List[str]:
        lines = []
        for worker in self.workqueue.workers:
            status = worker.status
            if status != worker.IDLE_STATUS:
                lines.append(status)
        return lines


def get_build_progress_ui(console: ndk.ansi.Console, workqueue: AnyWorkQueue) -> Ui:
    """Returns the appropriate build console UI for the given console."""
    ui_renderer: UiRenderer
    if console.smart_console:
        ui_renderer = AnsiUiRenderer(console)
        return BuildProgressUi(ui_renderer, workqueue)
    ui_renderer = NonAnsiUiRenderer(console)
    return NonAnsiBuildProgressUi(ui_renderer)


class NonAnsiBuildProgressUi(Ui):
    """A UI for displaying build status to non-ANSI consoles."""

    def get_ui_lines(self) -> List[str]:
        return []

    def clear(self) -> None:
        pass

    def draw(self) -> None:
        # Don't flood the terminal with repeated status of what is still
        # building. It will be printing the same three modules for most of the
        # build.
        pass


class TaskProgressUi(ABC):
    @abstractmethod
    def start_task(self, description: str) -> None:
        pass

    @abstractmethod
    def finish_task(self, description: str) -> None:
        pass

    @abstractmethod
    @contextmanager
    def context(self) -> Iterator[None]:
        pass


class BasicTaskProgressUi(TaskProgressUi):
    def start_task(self, description: str) -> None:
        print(f"{description}...")

    def finish_task(self, description: str) -> None:
        print(f"Finished {description}")

    @contextmanager
    def context(self) -> Iterator[None]:
        yield


try:
    from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

    CAN_USE_RICH = True

    class RichTaskProgressUi(TaskProgressUi):
        def __init__(self) -> None:
            self.progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
            )
            self.task_ids: dict[str, TaskID] = {}

        def start_task(self, description: str) -> None:
            if description in self.task_ids:
                raise KeyError(f"Duplicate task: {description}")
            self.task_ids[description] = self.progress.add_task(description, total=None)

        def finish_task(self, description: str) -> None:
            self.progress.update(self.task_ids[description], completed=True, total=1)

        @contextmanager
        def context(self) -> Iterator[None]:
            with self.progress:
                yield

except ModuleNotFoundError:
    CAN_USE_RICH = False


def get_task_progress_ui() -> TaskProgressUi:
    if CAN_USE_RICH and ndk.ansi.get_console().smart_console:
        return RichTaskProgressUi()
    return BasicTaskProgressUi()
