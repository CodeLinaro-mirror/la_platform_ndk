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

import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, List

import ndk.ansi
from ndk.ansi import Console, font_bold, font_faint, font_reset
from ndk.devenv.devices import Device, DeviceShardingGroup
from ndk.ui import AnsiUiRenderer, NonAnsiUiRenderer, UiRenderer
from ndk.workqueue import ShardingWorkQueue, Worker

from .devicetest.testrun import TestRun
from .printers import Printer
from .result import TestResult


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


def get_test_progress_ui(
    console: Console,
    workqueue: ShardingWorkQueue[Any, Device],
    printer: Printer,
    log_all_results: bool,
) -> TestProgressUi:
    ui_renderer: UiRenderer
    if console.smart_console:
        ui_renderer = AnsiUiRenderer(console)
        show_worker_status = True
        show_device_groups = True
    elif os.name == "nt":
        ui_renderer = NonAnsiUiRenderer(console)
        show_worker_status = False
        show_device_groups = False
    else:
        ui_renderer = NonAnsiUiRenderer(console)
        show_worker_status = False
        show_device_groups = True
    return WorkQueueTestProgressUi(
        ui_renderer,
        printer,
        console,
        log_all_results,
        show_worker_status,
        show_device_groups,
        workqueue,
    )
