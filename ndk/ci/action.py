# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod


class Action(ABC):
    """Base class for all CI actions."""

    @abstractmethod
    def run(self) -> None:
        """Runs the action.

        Any errors in the action should be raised as exceptions, or the action should
        call sys.exit() to exit with an error code.
        """
