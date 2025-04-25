# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import pprint
import shlex
import sys

from .action import Action
from .buildaction import BuildAction
from .ciconfig import CiConfig
from .testbuildaction import TestBuildAction


class App:
    """Determines and runs the CI tasks for the current build target.

    All CI actions run through this application, and the actions to take are determined
    based on the target name.
    """

    def run(self) -> None:
        """Runs the application."""
        config = CiConfig.from_argv()
        print(f"Running {shlex.join(sys.argv)}")
        print(f"Parsed build configuration: {pprint.pformat(config)}")
        action = self._action_from_args(config)
        action.run()

    def _action_from_args(self, config: CiConfig) -> Action:
        """Returns the action for the given branch and target."""
        match config.target:
            case "win64_tests":
                return TestBuildAction(config.build_id, config.dist_dir)
            case "win64":
                return BuildAction(config.build_id, config.dist_dir, host="windows64")
            case _:
                return BuildAction(config.build_id, config.dist_dir)
