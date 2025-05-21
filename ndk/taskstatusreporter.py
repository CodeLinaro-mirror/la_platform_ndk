# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Generic, TypeVar

TaskT = TypeVar("TaskT")


class TaskStatusReporter(Generic[TaskT]):
    def __init__(self) -> None:
        # This assumes that the string representation of the task will be
        # unique. If that assumption is wrong, it really ought to be for UI
        # reasons anyway, so fix the task type's __str__, not this.
        self.running_tasks: dict[TaskT, datetime] = {}

    def report_task_started(self, task: TaskT) -> None:
        self.running_tasks[task] = datetime.now()

    def report_task_finished(self, task: TaskT) -> None:
        del self.running_tasks[task]

    def iter_longest_running_tasks(
        self, num_tasks: int | None = None
    ) -> Iterator[tuple[TaskT, datetime]]:
        # Dictionaries iterate in insertion order, so this is conveniently
        # already sorted by the oldest task without needing to rely on a more
        # complicated data structure.
        for num, (task, start_time) in enumerate(self.running_tasks.items()):
            if num_tasks is not None and num >= num_tasks:
                return

            yield task, start_time

    @contextmanager
    def task_run_context(self, task: TaskT) -> Iterator[None]:
        self.report_task_started(task)
        try:
            yield
        finally:
            self.report_task_finished(task)
