# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager

import ndk.ansi
from ndk.test.printers import Printer
from ndk.test.result import TestResult
from ndk.ui import AnsiUiRenderer, NonAnsiUiRenderer, UiRenderer, WorkQueueUi
from ndk.workqueue import AnyWorkQueue


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
        printer: Printer,
        log_all_results: bool,
    ) -> None:
        self.console = ndk.ansi.get_console()
        self.printer = printer
        self.log_all_results = log_all_results

        ui_renderer: UiRenderer
        if self.console.smart_console:
            ui_renderer = AnsiUiRenderer(self.console)
            show_worker_status = True
        else:
            ui_renderer = NonAnsiUiRenderer(self.console)
            show_worker_status = False
        self.wrapped_ui = WorkQueueUi(ui_renderer, show_worker_status, workqueue)

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


def get_test_build_ui(
    workqueue: AnyWorkQueue, printer: Printer, log_all_results: bool
) -> TestBuildProgressUi:
    return WorkQueueTestBuildUi(workqueue, printer, log_all_results)
