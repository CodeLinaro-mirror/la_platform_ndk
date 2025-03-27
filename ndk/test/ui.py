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
from typing import Any, List

from ndk.ansi import Console, font_bold, font_faint, font_reset
from ndk.test.devices import Device
from ndk.ui import AnsiUiRenderer, NonAnsiUiRenderer, Ui, UiRenderer
from ndk.workqueue import ShardingWorkQueue, Worker


class TestProgressUi(Ui):
    NUM_TESTS_DIGITS = 6

    def __init__(
        self,
        ui_renderer: UiRenderer,
        show_worker_status: bool,
        show_device_groups: bool,
        workqueue: ShardingWorkQueue[Any, Device],
    ) -> None:
        super().__init__(ui_renderer)
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


def get_test_progress_ui(
    console: Console, workqueue: ShardingWorkQueue[Any, Device]
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
    return TestProgressUi(
        ui_renderer, show_worker_status, show_device_groups, workqueue
    )
