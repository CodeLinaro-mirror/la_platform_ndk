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

from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import ndk.ansi
from ndk.builds import Module

from .taskstatusreporter import TaskStatusReporter


class BuildProgressUi(ABC):
    """Console UI base class."""

    @abstractmethod
    @contextmanager
    def context(self) -> Iterator[None]:
        pass

    @abstractmethod
    def start_build(self, module: Module) -> None:
        pass

    @abstractmethod
    def finish_build(self, module: Module) -> None:
        pass

    @abstractmethod
    def report_failure(self, module: Module) -> None:
        pass

    @abstractmethod
    def finish(self) -> None:
        pass


class BasicBuildProgressUi(BuildProgressUi):
    """A UI for displaying build status to non-ANSI consoles."""

    @contextmanager
    def context(self) -> Iterator[None]:
        yield

    def start_build(self, module: Module) -> None:
        print(f"Building {module}...")

    def finish_build(self, module: Module) -> None:
        print(f"Finished building {module}")

    def report_failure(self, module: Module) -> None:
        print(f"Build failed: {module}")

    def finish(self) -> None:
        print("Build finished")


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
    from rich.console import Group
    from rich.live import Live
    from rich.markup import escape
    from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn
    from rich.table import Table

    CAN_USE_RICH = True

    class RichBuildProgressUi(BuildProgressUi):
        def __init__(self, task_status_reporter: TaskStatusReporter[Module]) -> None:
            self.task_status_reporter = task_status_reporter
            self.progress = Progress()
            self.longest_running_builds_table = Table()
            self.live = Live(get_renderable=self._ui_elements)
            self.task_id = self.progress.add_task("Building", total=None)
            self.total_tasks = 0

        @contextmanager
        def context(self) -> Iterator[None]:
            with self.live:
                yield

        def start_build(self, module: Module) -> None:
            self.total_tasks += 1
            self.progress.update(self.task_id, total=self.total_tasks)

        def finish_build(self, module: Module) -> None:
            self.progress.advance(self.task_id)

        def report_failure(self, module: Module) -> None:
            self.progress.console.print(f"Build failed: {module}")

        def finish(self) -> None:
            pass

        def _ui_elements(self) -> Group:
            table = Table(
                "Duration",
                "Test",
                title="Long running tasks",
                title_justify="left",
                title_style="",
                box=None,
                show_header=False,
                show_edge=False,
                show_lines=False,
            )
            now = datetime.now()
            for (
                test,
                start_time,
            ) in self.task_status_reporter.iter_longest_running_tasks(5):
                elapsed = now - start_time
                if elapsed < timedelta(seconds=1):
                    break
                total_seconds = elapsed.total_seconds()
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                table.add_row(f"{minutes:02}:{seconds:02}", escape(str(test)))

            return Group(self.progress, table)

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


def get_build_progress_ui(
    task_status_reporter: TaskStatusReporter[Module],
) -> BuildProgressUi:
    """Returns the appropriate build console UI for the given console."""
    console = ndk.ansi.get_console()
    if console.smart_console and CAN_USE_RICH:
        return RichBuildProgressUi(task_status_reporter)
    return BasicBuildProgressUi()


def get_task_progress_ui() -> TaskProgressUi:
    if CAN_USE_RICH and ndk.ansi.get_console().smart_console:
        return RichTaskProgressUi()
    return BasicTaskProgressUi()
