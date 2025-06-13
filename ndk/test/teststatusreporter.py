# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from .buildtest.case import Test


class TestStatusReporter:
    def __init__(self) -> None:
        # This assumes that the string representation of the test will be
        # unique. If that assumption is wrong, it really ought to be for UI
        # reasons anyway, so fix Test.__str__, not this.
        self.running_tests: dict[Test, datetime] = {}

    def report_test_started(self, test: Test) -> None:
        self.running_tests[test] = datetime.now()

    def report_test_finished(self, test: Test) -> None:
        del self.running_tests[test]

    def iter_longest_running_tests(
        self, num_tests: int | None = None
    ) -> Iterator[tuple[Test, datetime]]:
        # Dictionaries iterate in insertion order, so this is conveniently
        # already sorted by the oldest test without needing to rely on a more
        # complicated data structure.
        for num, (test, start_time) in enumerate(self.running_tests.items()):
            if num_tests is not None and num >= num_tests:
                return

            yield test, start_time

    @contextmanager
    def test_run_context(self, test: Test) -> Iterator[None]:
        self.report_test_started(test)
        try:
            yield
        finally:
            self.report_test_finished(test)
