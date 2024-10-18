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
"""Timer APIs."""
import datetime
import timeit
from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Optional, Type


class Timer:
    """Execution timer.

    Can be used explicitly with stop/start, but preferably is used as a context
    manager:

    >>> def timer_example():
    ...     timer = Timer()
    ...     with timer:
    ...         do_something()
    ...     print(f'do_something() took {timer.duration}.')
    """

    def __init__(self) -> None:
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration: Optional[datetime.timedelta] = None

    def start(self) -> None:
        """Start the timer."""
        self.start_time = timeit.default_timer()

    def finish(self) -> None:
        """Stop the timer."""
        assert self.start_time is not None
        self.end_time = timeit.default_timer()

        # Not interested in partial seconds at this scale.
        seconds = int(self.end_time - self.start_time)
        self.duration = datetime.timedelta(seconds=seconds)

    def __enter__(self) -> None:
        self.start()

    def __exit__(
        self,
        _exc_type: Optional[Type[BaseException]],
        _exc_value: Optional[BaseException],
        _traceback: Optional[TracebackType],
    ) -> None:
        self.finish()


class TimingReport:
    def __init__(self) -> None:
        self.times: dict[str, datetime.timedelta] = {}

    def add_timing_report(self, label: str, timer: Timer) -> None:
        if label in self.times:
            raise ValueError(f"Duplicate timing report for {label}")
        assert timer.duration is not None
        self.times[label] = timer.duration

    @contextmanager
    def timed(self, description: str) -> Iterator[None]:
        timer = Timer()
        with timer:
            yield
        self.add_timing_report(description, timer)
