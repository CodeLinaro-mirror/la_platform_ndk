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
"""Helpers for subprocess APIs."""
from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Sequence, Tuple
from pathlib import Path
import asyncio
import shlex

# TODO: Remove in favor of subprocess.run.


def logger() -> logging.Logger:
    """Returns the logger for this module."""
    return logging.getLogger(__name__)


def _call_output_inner(
    cmd: Sequence[str], *args: Any, **kwargs: Any
) -> Tuple[int, Any]:
    """Does the real work of call_output.

    This inner function does the real work and the outer function handles the
    OS specific stuff (Windows needs to handle WindowsError, but that isn't
    defined on non-Windows systems).
    """
    logger().info("Popen: %s", " ".join(cmd))
    kwargs.update(
        {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
    )
    with subprocess.Popen(cmd, *args, **kwargs) as proc:
        out, _ = proc.communicate()
        return proc.returncode, out


def call_output(cmd: Sequence[str], *args: Any, **kwargs: Any) -> Tuple[int, Any]:
    """Invoke the specified command and return exit code and output.

    This is the missing subprocess.call_output, which is the combination of
    subprocess.call and subprocess.check_output. Like call, it returns an exit
    code rather than raising an exception. Like check_output, it returns the
    output of the program. Unlike check_output, it returns the output even on
    failure.

    Returns: Tuple of (exit_code, output).
    """
    if sys.platform == "win32":
        try:
            return _call_output_inner(cmd, *args, **kwargs)
        except WindowsError as error:  # pylint: disable=undefined-variable
            return error.winerror, error.strerror
    else:
        return _call_output_inner(cmd, *args, **kwargs)


@contextmanager
def verbose_subprocess_errors() -> Iterator[None]:
    try:
        yield
    except subprocess.CalledProcessError as ex:
        if ex.stdout is not None:
            ex.add_note(f"stdout:\n{ex.stdout}")
        if ex.stderr is not None:
            ex.add_note(f"stderr:\n{ex.stderr}")
        raise


async def async_run(
    cmd: Sequence[str | Path], check: bool, cwd: Path | None = None
) -> asyncio.subprocess.Process:
    """Runs and logs an asyncio subprocess."""
    logger().debug("exec CWD=%s %s", cwd or Path.cwd(), shlex.join(str(a) for a in cmd))
    proc = await asyncio.create_subprocess_exec(cmd[0], *cmd[1:], cwd=cwd)
    await proc.communicate()
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: CWD={cwd or Path.cwd()} {shlex.join(str(a) for a in cmd)}"
        )
    return proc
