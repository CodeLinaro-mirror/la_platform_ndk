#
# Copyright (C) 2016 The Android Open Source Project
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
"""Debugging tools for NDK build and test libraries."""
import pdb
import signal
import sys
import traceback
from types import FrameType
from typing import Optional


def attach_debugger(_signum: int, frame: Optional[FrameType]) -> None:
    """Attaches pdb to the frame at the time of signalling."""
    # mypy doesn't know that pdb.Pdb exists.
    pdb.Pdb().set_trace(frame)


def dump_trace(_signum: int, frame: Optional[FrameType]) -> None:
    """Dumps a stack trace of the frame at the time of signalling."""
    msg = "Traceback:\n"
    msg += "".join(traceback.format_stack(frame))
    sys.stderr.write(msg)


def register_debug_handler(signum: int) -> None:
    """Registers a signal handler that will attach the debugger.

    Args:
        signum: Signal on which to attach the debugger.
    """
    signal.signal(signum, attach_debugger)


def register_trace_handler(signum: int) -> None:
    """Registers a signal that will dump a stack trace.

    Args:
        signum: Signal on which to dump a stack trace.
    """
    signal.signal(signum, dump_trace)
