# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""UI classes for test output."""
from __future__ import absolute_import, print_function

from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta

from rich.progress import Progress, TaskID

from ndk.ansi import Console
from ndk.devenv.devices import DeviceShardingGroup
from ndk.test.printers import Printer
from ndk.test.result import TestResult
from ndk.test.richtextcolorer import rich_text_colorer

from .testrun import TestRun


class TestProgressUi(ABC):
    @contextmanager
    @abstractmethod
    def ui_context(self) -> Iterator[None]:
        """Enters the UI updating context."""

    @abstractmethod
    def on_test_scheduled(self, test: TestRun) -> None:
        """Called when a test run is scheduled."""

    @abstractmethod
    def on_test_finished(
        self, device_group: DeviceShardingGroup, result: TestResult
    ) -> None:
        """Called when a test is completed."""

    @abstractmethod
    def on_finished(self) -> None:
        """Called when all tests are completed."""


class RichTestProgressUi(TestProgressUi):
    def __init__(self, log_all_results: bool) -> None:
        self.log_all_results = log_all_results
        self.progress = Progress()
        self.jobs_per_group: dict[DeviceShardingGroup, int] = defaultdict(int)
        self.task_ids: dict[DeviceShardingGroup, TaskID] = {}

    @contextmanager
    def ui_context(self) -> Iterator[None]:
        for device_group, task_id in self.task_ids.items():
            self.progress.update(task_id, total=self.jobs_per_group[device_group])

        with self.progress:
            yield

    def on_test_scheduled(self, test: TestRun) -> None:
        group = test.device_group
        self.jobs_per_group[group] += 1
        if group not in self.task_ids:
            self.task_ids[group] = self.progress.add_task(
                f"Running tests on {group}", total=None
            )

    def on_test_finished(
        self, device_group: DeviceShardingGroup, result: TestResult
    ) -> None:
        if self.log_all_results or result.failed():
            self.progress.console.print(
                result.to_string(colored=True, text_colorer=rich_text_colorer)
            )
        self.progress.advance(self.task_ids[device_group])

    def on_finished(self) -> None:
        pass


class BasicTestProgressUi(TestProgressUi):
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

    def on_test_scheduled(self, test: TestRun) -> None:
        self.remaining += 1

    def on_test_finished(
        self, device_group: DeviceShardingGroup, result: TestResult
    ) -> None:
        if self.log_all_results or result.failed():
            self.printer.print_result(result)
        self.remaining -= 1
        now = datetime.now()
        if now - self.last_log >= self.log_period:
            self.last_log = now
            print(f"{self.remaining} tests remaining")

    def on_finished(self) -> None:
        pass


def get_test_progress_ui(
    console: Console,
    printer: Printer,
    log_all_results: bool,
) -> TestProgressUi:
    if console.smart_console:
        return RichTestProgressUi(log_all_results)
    return BasicTestProgressUi(printer, log_all_results)
