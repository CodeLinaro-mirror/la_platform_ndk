# Copyright (C) 2024 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
import subprocess
from asyncio import TaskGroup
from pathlib import PurePosixPath

from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn

import ndk.paths
from ndk.devenv.devices import Device, DeviceFleet

from .testgroup import TestGroup
from .testplan import TestPlan


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


async def clear_test_directory(task_id: TaskID, device: Device) -> TaskID:
    cmd = ["rm", "-r", str(ndk.paths.DEVICE_TEST_BASE_DIR)]
    logger().info('%s: shell_nocheck "%s"', device.product_name, cmd)
    await device.shell_nocheck(cmd)
    return task_id


def adb_has_feature(feature: str) -> bool:
    cmd = ["adb", "host-features"]
    logger().info('check_output "%s"', " ".join(cmd))
    output = subprocess.check_output(cmd).decode("utf-8")
    features_line = output.splitlines()[-1]
    features = features_line.split(",")
    return feature in features


async def push_test_group_to_device(
    test_group: TestGroup,
    dest_dir: PurePosixPath,
    device: Device,
    use_sync: bool,
) -> None:
    """Pushes a directory to the given device.

    Creates the parent directory on the device if needed.

    Args:
        worker: The worker performing the task.
        test_group: The group of tests to push.
        dest_dir: The destination directory on the device. Note that when
                  pushing a directory, dest_dir will be the parent directory,
                  not the destination path.
        device: The device to push to.
        use_sync: True if `adb push --sync` is supported.
    """
    logger().info(
        "%s: push%s %s %s",
        device.product_name,
        " --sync" if use_sync else "",
        test_group.host_path,
        dest_dir,
    )
    await device.push(str(test_group.host_path), str(dest_dir), sync=use_sync)
    # Tests that were built and bundled on Windows but pushed from Linux or macOS will
    # not have execute permission by default. Since we don't know where the tests came
    # from, chmod all the tests regardless.
    await device.shell(["chmod", "-R", "777", str(dest_dir)])


async def push_tests_to_device(
    task_id: TaskID,
    test_groups: list[TestGroup],
    dest_dir: PurePosixPath,
    device: Device,
    use_sync: bool,
) -> TaskID:
    """Pushes a directory to the given device.

    Creates the parent directory on the device if needed.

    Args:
        worker: The worker performing the task.
        test_groups: The groups of tests to push.
        dest_dir: The destination directory on the device. Note that when
                  pushing a directory, dest_dir will be the parent directory,
                  not the destination path.
        device: The device to push to.
        use_sync: True if `adb push --sync` is supported.
    """
    logger().info("%s: mkdir %s", device.product_name, dest_dir)
    await device.shell_nocheck(["mkdir", str(dest_dir)])

    async with TaskGroup() as tasks:
        for group in test_groups:
            tasks.create_task(
                push_test_group_to_device(group, dest_dir, device, use_sync)
            )
    return task_id


class DevicePreparer:
    def __init__(self, fleet: DeviceFleet) -> None:
        self.fleet = fleet

    async def clean(self) -> None:
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
        )
        with progress:
            tasks = []
            for group in self.fleet.get_unique_device_groups():
                for device in group.devices:
                    task_id = progress.add_task(
                        f"Cleaning test directory on {device}", total=None
                    )
                    tasks.append(
                        asyncio.create_task(clear_test_directory(task_id, device))
                    )

            for task in asyncio.as_completed(tasks):
                task_id = await task
                progress.update(task_id, completed=True, total=1)

    async def push(self, test_plan: TestPlan) -> None:
        can_use_sync = adb_has_feature("push_sync")
        dest_dir = ndk.paths.DEVICE_TEST_BASE_DIR
        tasks = []

        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
        )
        with progress:
            for group in self.fleet.get_unique_device_groups():
                test_groups = []
                for test_group in test_plan.iter_test_groups():
                    if group.can_run_build_config(test_group.build_config):
                        test_groups.append(test_group)

                for device in group.devices:
                    task_id = progress.add_task(
                        f"Pushing tests to {device}", total=None
                    )
                    tasks.append(
                        asyncio.create_task(
                            push_tests_to_device(
                                task_id,
                                test_groups,
                                dest_dir,
                                device,
                                can_use_sync,
                            )
                        )
                    )

            for task in asyncio.as_completed(tasks):
                task_id = await task
                progress.update(task_id, completed=True, total=1)
