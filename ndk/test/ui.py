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
"""UI classes for test output."""
from __future__ import absolute_import, print_function

import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, List

from rich.progress import Progress, TaskID

import ndk.ansi
from ndk.ansi import Console, font_bold, font_faint, font_reset
from ndk.devenv.devices import Device, DeviceShardingGroup
from ndk.ui import AnsiUiRenderer, UiRenderer
from ndk.workqueue import ShardingWorkQueue, Worker

from .devicetest.testrun import TestRun
from .printers import Printer
from .result import TestResult

USE_RICH = True


def rich_text_colorer(text: str, color: str, do_color: bool) -> str:
    if do_color:
        return f"[{color}]{text}[/{color}]"
    return text


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


class WorkQueueTestProgressUi(TestProgressUi):
    NUM_TESTS_DIGITS = 6

    def __init__(
        self,
        ui_renderer: UiRenderer,
        printer: Printer,
        console: Console,
        log_all_results: bool,
        show_worker_status: bool,
        show_device_groups: bool,
        workqueue: ShardingWorkQueue[Any, Device],
    ) -> None:
        self.ui_renderer = ui_renderer
        self.printer = printer
        self.console = console
        self.log_all_results = log_all_results
        self.show_worker_status = show_worker_status
        self.show_device_groups = show_device_groups
        self.workqueue = workqueue

    def get_ui_lines(self) -> List[str]:
        lines = []

        if self.show_worker_status:
            for group, group_queues in self.workqueue.work_queues.items():
                for device, work_queue in group_queues.items():
                    style = font_bold()
                    if all(w.status == Worker.IDLE_STATUS for w in work_queue.workers):
                        style = font_faint()
                    lines.append(f"{style}{device}{font_reset()}")
                    for worker in work_queue.workers:
                        style = ""
                        if worker.status == Worker.IDLE_STATUS:
                            style = font_faint()
                        lines.append(f"  {style}{worker.status}{font_reset()}")

        lines.append(
            "{: >{width}} tests remaining".format(
                self.workqueue.num_tasks, width=self.NUM_TESTS_DIGITS
            )
        )

        if self.show_device_groups:
            for group in sorted(self.workqueue.task_queues.keys(), key=str):
                group_id = f"{len(group.shards)} devices {group}"
                lines.append(
                    "{: >{width}} {}".format(
                        self.workqueue.task_queues[group].qsize(),
                        group_id,
                        width=self.NUM_TESTS_DIGITS,
                    )
                )

        return lines

    def clear(self) -> None:
        """Clears the UI."""
        self.ui_renderer.clear_last_render()

    def draw(self) -> None:
        """Draws the UI."""
        self.ui_renderer.render(self.get_ui_lines())

    @contextmanager
    def ui_context(self) -> Iterator[None]:
        with ndk.ansi.disable_terminal_echo(sys.stdin):
            with self.console.cursor_hide_context():
                yield

    def on_test_scheduled(self, test: TestRun) -> None:
        pass

    def on_test_finished(
        self, device_group: DeviceShardingGroup, result: TestResult
    ) -> None:
        if self.log_all_results or result.failed():
            self.clear()
            self.printer.print_result(result)
        self.draw()

    def on_finished(self) -> None:
        self.clear()


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
    workqueue: ShardingWorkQueue[Any, Device],
    printer: Printer,
    log_all_results: bool,
) -> TestProgressUi:
    if USE_RICH and console.smart_console:
        return RichTestProgressUi(log_all_results)

    if console.smart_console:
        return WorkQueueTestProgressUi(
            AnsiUiRenderer(console),
            printer,
            console,
            log_all_results,
            show_worker_status=True,
            show_device_groups=True,
            workqueue=workqueue,
        )
    return BasicTestProgressUi(printer, log_all_results)
