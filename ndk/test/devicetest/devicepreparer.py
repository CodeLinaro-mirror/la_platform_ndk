#
# Copyright (C) 2024 The Android Open Source Project
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
import logging
import subprocess
from pathlib import PurePosixPath

import ndk.ui

# TODO: This module should be moved into ndk.devenv.
from ndk.devenv.devices import Device, DeviceFleet
from ndk.workqueue import Worker, WorkQueue

from .testgroup import TestGroup
from .testplan import TestPlan


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def clear_test_directory(_worker: Worker, device: Device) -> None:
    print(f"Clearing test directory on {device}")
    cmd = ["rm", "-r", str(ndk.paths.DEVICE_TEST_BASE_DIR)]
    logger().info('%s: shell_nocheck "%s"', device.product_name, cmd)
    device.shell_nocheck(cmd)


def adb_has_feature(feature: str) -> bool:
    cmd = ["adb", "host-features"]
    logger().info('check_output "%s"', " ".join(cmd))
    output = subprocess.check_output(cmd).decode("utf-8")
    features_line = output.splitlines()[-1]
    features = features_line.split(",")
    return feature in features


def push_tests_to_device(
    worker: Worker,
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
    worker.status = f"Pushing {test_group.build_config} tests to {device}."
    logger().info("%s: mkdir %s", device.product_name, dest_dir)
    device.shell_nocheck(["mkdir", str(dest_dir)])
    logger().info(
        "%s: push%s %s %s",
        device.product_name,
        " --sync" if use_sync else "",
        test_group.host_path,
        dest_dir,
    )
    device.push(str(test_group.host_path), str(dest_dir), sync=use_sync)
    # Tests that were built and bundled on Windows but pushed from Linux or macOS will
    # not have execute permission by default. Since we don't know where the tests came
    # from, chmod all the tests regardless.
    device.shell(["chmod", "-R", "777", str(dest_dir)])


class DevicePreparer:
    def __init__(self, fleet: DeviceFleet) -> None:
        self.fleet = fleet

    def clean(self, workqueue: WorkQueue) -> None:
        for group in self.fleet.get_unique_device_groups():
            for device in group.devices:
                workqueue.add_task(clear_test_directory, device)

        while not workqueue.finished():
            workqueue.get_result()

    def push(self, workqueue: WorkQueue, test_plan: TestPlan) -> None:
        can_use_sync = adb_has_feature("push_sync")
        dest_dir = ndk.paths.DEVICE_TEST_BASE_DIR
        for test_group in test_plan.iter_test_groups():
            for group in self.fleet.get_unique_device_groups():
                if group.can_run_build_config(test_group.build_config):
                    for device in group.devices:
                        workqueue.add_task(
                            push_tests_to_device,
                            test_group,
                            dest_dir,
                            device,
                            can_use_sync,
                        )

        ndk.ui.finish_workqueue_with_ui(workqueue, ndk.ui.get_work_queue_ui)
