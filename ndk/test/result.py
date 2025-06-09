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
"""Test result classes."""
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import ndk.termcolor

# TODO: Need to resolve the circular import between this and ndk.test.types.
Test = Any


@dataclass(frozen=True)
class ResultTranslations:
    success: str = "PASS"
    failure: str = "FAIL"
    skip: str = "SKIP"
    expected_failure: str = "KNOWN FAIL"
    unexpected_success: str = "SHOULD FAIL"


class TestResult:
    def __init__(self, test: Test):
        self.test = test

    def __repr__(self) -> str:
        return self.to_string(colored=False)

    def passed(self) -> bool:
        raise NotImplementedError

    def failed(self) -> bool:
        raise NotImplementedError

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        raise NotImplementedError


UserDataT = TypeVar("UserDataT")


class Failure(TestResult, Generic[UserDataT]):
    def __init__(
        self,
        test: Test,
        message: str,
        repro_cmd: str | None = None,
        user_data: UserDataT | None = None,
    ) -> None:
        super().__init__(test)
        self.message = message
        self.repro_cmd = repro_cmd
        self._user_data = user_data

    @property
    def user_data(self) -> UserDataT:
        assert self._user_data is not None
        return self._user_data

    def passed(self) -> bool:
        return False

    def failed(self) -> bool:
        return True

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        label = ndk.termcolor.maybe_color(tr.failure, "red", colored)
        repro = f" {self.repro_cmd}" if self.repro_cmd else ""
        return f"{label} {self.test}:{repro}\n" f"{self.message}"


class Success(TestResult):
    def passed(self) -> bool:
        return True

    def failed(self) -> bool:
        return False

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        label = ndk.termcolor.maybe_color(tr.success, "green", colored)
        return f"{label} {self.test}"


class Skipped(TestResult):
    def __init__(self, test: Test, reason: str) -> None:
        super().__init__(test)
        self.reason = reason

    def passed(self) -> bool:
        return False

    def failed(self) -> bool:
        return False

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        label = ndk.termcolor.maybe_color(tr.skip, "yellow", colored)
        return f"{label} {self.test}: {self.reason}"


class ExpectedFailure(TestResult):
    def __init__(self, test: Test, message: str, broken_config: str, bug: str) -> None:
        super().__init__(test)
        self.message = message
        self.broken_config = broken_config
        self.bug = bug

    def passed(self) -> bool:
        return True

    def failed(self) -> bool:
        return False

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        label = ndk.termcolor.maybe_color(tr.expected_failure, "yellow", colored)
        return (
            f"{label} {self.test}: known failure "
            f"for {self.broken_config} ({self.bug}): {self.message}"
        )


class UnexpectedSuccess(TestResult):
    def __init__(self, test: Test, broken_config: str, bug: str) -> None:
        super().__init__(test)
        self.broken_config = broken_config
        self.bug = bug

    def passed(self) -> bool:
        return False

    def failed(self) -> bool:
        return True

    def to_string(
        self, tr: ResultTranslations = ResultTranslations(), colored: bool = False
    ) -> str:
        label = ndk.termcolor.maybe_color(tr.unexpected_success, "red", colored)
        return (
            f"{label} {self.test}: "
            f"unexpected success for {self.broken_config} ({self.bug})"
        )
