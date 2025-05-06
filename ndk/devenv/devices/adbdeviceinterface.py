# Copyright (C) 2015 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import subprocess


class FindDeviceError(RuntimeError):
    pass


class DeviceNotFoundError(FindDeviceError):
    def __init__(self, serial: str) -> None:
        self.serial = serial
        super().__init__(f"No device with serial {serial}")


class NoUniqueDeviceError(FindDeviceError):
    def __init__(self) -> None:
        super().__init__("No unique device")


class ShellError(RuntimeError):
    def __init__(
        self, cmd: list[str], stdout: str, stderr: str, exit_code: int
    ) -> None:
        super().__init__(f"`{cmd}` exited with code {exit_code}")
        self.cmd = cmd
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


class AdbDeviceInterface:
    # Delimiter string to indicate the start of the exit code.
    _RETURN_CODE_DELIMITER = "x"

    # Follow any shell command with this string to get the exit
    # status of a program since this isn't propagated by adb.
    #
    # The delimiter is needed because `printf 1; echo $?` would print
    # "10", and we wouldn't be able to distinguish the exit code.
    _RETURN_CODE_PROBE = [";", "echo", "{0}$?".format(_RETURN_CODE_DELIMITER)]

    # Maximum search distance from the output end to find the delimiter.
    # adb on Windows returns \r\n even if adbd returns \n. Some old devices
    # seem to actually return \r\r\n.
    _RETURN_CODE_SEARCH_LENGTH = len("{0}255\r\r\n".format(_RETURN_CODE_DELIMITER))

    def __init__(
        self, serial: str | None, product: str | None = None, adb_path: str = "adb"
    ) -> None:
        self.serial = serial
        self.product = product
        self.adb_path = adb_path
        self.adb_cmd = [adb_path]

        if self.serial is not None:
            self.adb_cmd.extend(["-s", self.serial])
        if self.product is not None:
            self.adb_cmd.extend(["-p", self.product])
        self._linesep: str | None = None

    def _make_shell_cmd(self, user_cmd: list[str]) -> list[str]:
        return self.adb_cmd + ["shell"] + user_cmd + self._RETURN_CODE_PROBE

    def _parse_shell_output(self, out: str) -> tuple[int, str]:
        """Finds the exit code string from shell output.

        Args:
            out: Shell output string.

        Returns:
            An (exit_code, output_string) tuple. The output string is
            cleaned of any additional stuff we appended to find the
            exit code.

        Raises:
            RuntimeError: Could not find the exit code in |out|.
        """
        search_text = out
        if len(search_text) > self._RETURN_CODE_SEARCH_LENGTH:
            # We don't want to search over massive amounts of data when we know
            # the part we want is right at the end.
            search_text = search_text[-self._RETURN_CODE_SEARCH_LENGTH :]
        partition = search_text.rpartition(self._RETURN_CODE_DELIMITER)
        if partition[1] == "":
            raise RuntimeError("Could not find exit status in shell output.")
        result = int(partition[2])
        # partition[0] won't contain the full text if search_text was
        # truncated, pull from the original string instead.
        out = out[: -len(partition[1]) - len(partition[2])]
        return result, out

    async def _simple_call(self, cmd: list[str]) -> str:
        logging.info(" ".join(self.adb_cmd + cmd))
        proc = await asyncio.create_subprocess_exec(
            *self.adb_cmd, *cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
        await proc.wait()
        return stdout.decode("utf-8")

    async def shell(self, cmd: list[str]) -> tuple[str, str]:
        """Calls `adb shell`

        Args:
            cmd: command to execute as a list of strings.

        Returns:
            A (stdout, stderr) tuple. Stderr may be combined into stdout
            if the device doesn't support separate streams.

        Raises:
            ShellError: the exit code was non-zero.
        """
        exit_code, stdout, stderr = await self.shell_nocheck(cmd)
        if exit_code != 0:
            raise ShellError(cmd, stdout, stderr, exit_code)
        return stdout, stderr

    async def shell_nocheck(self, cmd: list[str]) -> tuple[int, str, str]:
        """Calls `adb shell`

        Args:
            cmd: command to execute as a list of strings.

        Returns:
            An (exit_code, stdout, stderr) tuple. Stderr may be combined
            into stdout if the device doesn't support separate streams.
        """
        cmd = self._make_shell_cmd(cmd)
        logging.info(" ".join(cmd))
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout_bytes, stderr_bytes = await p.communicate()
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
        await p.wait()
        exit_code, stdout = self._parse_shell_output(stdout)
        return exit_code, stdout, stderr

    async def push(
        self,
        local: str | list[str],
        remote: str,
        sync: bool = False,
        parameters: list[str] | None = None,
    ) -> str:
        """Transfer a local file or directory to the device.

        Args:
            local: The local file or directory to transfer.
            remote: The remote path to which local should be transferred.
            sync: If True, only transfers files that are newer on the host than
                  those on the device. If False, transfers all files.

        Returns:
            Output of the command.
        """
        cmd = ["push"]
        if parameters is not None:
            cmd.extend(parameters)

        if sync:
            cmd.append("--sync")

        if isinstance(local, str):
            cmd.extend([local, remote])
        else:
            cmd.extend(local)
            cmd.append(remote)

        return await self._simple_call(cmd)

    async def sysprops(self) -> dict[str, str]:
        props = {}
        output = (await self.shell(["getprop"]))[0]
        for line in output.splitlines():
            # Values can include newlines, so keys and values are bracketed. For now it
            # seems like we don't need any of those properties, so just ignore them
            # rather than build the parser.
            if ": " not in line:
                continue
            decorated_key, decorated_value = line.split(": ")
            if decorated_value[-1] != "]":
                continue
            props[decorated_key[1:-1]] = decorated_value[1:-1]
        return props

    async def logcat(self) -> str:
        """Returns the contents of logcat."""
        return await self._simple_call(["logcat", "-d"])

    async def clear_logcat(self) -> None:
        """Clears the logcat buffer."""
        await self._simple_call(["logcat", "-c"])
