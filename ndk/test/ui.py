# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import ndk.ansi
from ndk.taskstatusreporter import TaskStatusReporter
from ndk.test.printers import Printer
from ndk.test.result import TestResult
from ndk.test.richtextcolorer import rich_text_colorer

from .buildtest.case import Test


class TestBuildProgressUi(ABC):
    @contextmanager
    @abstractmethod
    def ui_context(self) -> Iterator[None]:
        """Enters the UI updating context."""

    @abstractmethod
    def on_task_scheduled(self) -> None:
        """Called when a test build is scheduled."""

    @abstractmethod
    def on_task_finished(self, result: TestResult) -> None:
        """Called when a test build is completed."""

    @abstractmethod
    def on_finished(self) -> None:
        """Called when all test builds are completed."""


try:
    from rich.console import Group
    from rich.live import Live
    from rich.markup import escape
    from rich.progress import Progress
    from rich.table import Table

    CAN_USE_RICH = True

    class RichTestBuildUi(TestBuildProgressUi):
        def __init__(
            self, test_status_reporter: TaskStatusReporter[Test], log_all_results: bool
        ) -> None:
            self.test_status_reporter = test_status_reporter
            self.log_all_results = log_all_results
            self.progress = Progress()
            self.longest_running_builds_table = Table()
            self.live = Live(get_renderable=self._ui_elements)
            self.total = 0
            self.task_id = self.progress.add_task("Building tests", total=None)

        @contextmanager
        def ui_context(self) -> Iterator[None]:
            self.progress.update(self.task_id, total=self.total)
            with self.live:
                yield

        def on_task_scheduled(self) -> None:
            self.total += 1

        def on_task_finished(self, result: TestResult) -> None:
            if self.log_all_results or result.failed():
                self.progress.console.print(
                    result.to_string(
                        colored=True, text_colorer=rich_text_colorer, escape=escape
                    )
                )
            self.progress.advance(self.task_id)

        def on_finished(self) -> None:
            pass

        def _ui_elements(self) -> Group:
            table = Table(
                "Duration",
                "Test",
                title="Long running tests",
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
            ) in self.test_status_reporter.iter_longest_running_tasks(5):
                elapsed = now - start_time
                if elapsed < timedelta(seconds=1):
                    break
                total_seconds = elapsed.total_seconds()
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                table.add_row(f"{minutes:02}:{seconds:02}", escape(str(test)))

            return Group(self.progress, table)

except ModuleNotFoundError:
    CAN_USE_RICH = False


class BasicTestBuildUi(TestBuildProgressUi):
    def __init__(
        self,
        printer: Printer,
        log_all_results: bool,
        log_period: timedelta = timedelta(seconds=5),
    ) -> None:
        self.printer = printer
        self.log_all_results = log_all_results
        self.remaining = 0
        self.start_time = datetime.now()
        self.last_log = self.start_time
        self.log_period = log_period

    @contextmanager
    def ui_context(self) -> Iterator[None]:
        print(f"{self.remaining} tests remaining")
        self.last_log = datetime.now()
        yield

    def on_task_scheduled(self) -> None:
        self.remaining += 1

    def on_task_finished(self, result: TestResult) -> None:
        if self.log_all_results or result.failed():
            self.printer.print_result(result)
        self.remaining -= 1
        now = datetime.now()
        if now - self.last_log >= self.log_period:
            self.last_log = now
            print(f"{self.remaining} tests remaining after {now - self.start_time}")

    def on_finished(self) -> None:
        pass


def get_test_build_ui(
    printer: Printer,
    build_status_reporter: TaskStatusReporter[Test],
    log_all_results: bool,
) -> TestBuildProgressUi:
    console = ndk.ansi.get_console()
    if console.smart_console and CAN_USE_RICH:
        return RichTestBuildUi(build_status_reporter, log_all_results)
    return BasicTestBuildUi(printer, log_all_results)
