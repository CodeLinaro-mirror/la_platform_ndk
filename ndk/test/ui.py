# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

import ndk.ansi
from ndk.ansi import Console
from ndk.test.printers import Printer
from ndk.test.result import TestResult
from ndk.test.richtextcolorer import rich_text_colorer
from ndk.ui import AnsiUiRenderer, WorkQueueUi
from ndk.workqueue import AnyWorkQueue

try:
    from rich.progress import Progress

    CAN_USE_RICH = True
except ModuleNotFoundError:
    CAN_USE_RICH = False


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


class WorkQueueTestBuildUi(TestBuildProgressUi):
    def __init__(
        self,
        workqueue: AnyWorkQueue,
        console: Console,
        printer: Printer,
        log_all_results: bool,
    ) -> None:
        if not console.smart_console:
            raise RuntimeError(
                "WorkQueueTestBuildUi can only be used with smart consoles"
            )

        self.console = ndk.ansi.get_console()
        self.printer = printer
        self.log_all_results = log_all_results
        self.wrapped_ui = WorkQueueUi(
            AnsiUiRenderer(self.console), show_worker_status=True, workqueue=workqueue
        )

    @contextmanager
    def ui_context(self) -> Iterator[None]:
        with ndk.ansi.disable_terminal_echo(sys.stdin):
            with self.console.cursor_hide_context():
                yield

    def on_task_scheduled(self) -> None:
        pass

    def on_task_finished(self, result: TestResult) -> None:
        if self.log_all_results or result.failed():
            self.wrapped_ui.clear()
            self.printer.print_result(result)
        self.wrapped_ui.draw()

    def on_finished(self) -> None:
        self.wrapped_ui.clear()


class RichTestBuildUi(TestBuildProgressUi):
    def __init__(self, log_all_results: bool) -> None:
        self.log_all_results = log_all_results
        self.progress = Progress()
        self.total = 0
        self.task_id = self.progress.add_task("Building tests", total=None)

    @contextmanager
    def ui_context(self) -> Iterator[None]:
        self.progress.update(self.task_id, total=self.total)
        with self.progress:
            yield

    def on_task_scheduled(self) -> None:
        self.total += 1

    def on_task_finished(self, result: TestResult) -> None:
        if self.log_all_results or result.failed():
            self.progress.console.print(
                result.to_string(colored=True, text_colorer=rich_text_colorer)
            )
        self.progress.advance(self.task_id)

    def on_finished(self) -> None:
        pass


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
        self.last_log = datetime.now()
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
            print(f"{self.remaining} tests remaining")

    def on_finished(self) -> None:
        pass


def get_test_build_ui(
    workqueue: AnyWorkQueue, printer: Printer, log_all_results: bool
) -> TestBuildProgressUi:
    console = ndk.ansi.get_console()
    if console.smart_console:
        if CAN_USE_RICH:
            return RichTestBuildUi(log_all_results)
        return WorkQueueTestBuildUi(workqueue, console, printer, log_all_results)
    return BasicTestBuildUi(printer, log_all_results)
