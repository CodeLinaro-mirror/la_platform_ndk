# Copyright (C) 2017 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
"""Device wrappers and device fleet management."""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List

from ndk.abis import Abi
from ndk.workqueue import Worker, WorkQueue

from .device import Device
from .devicefleet import DeviceFleet


def logger() -> logging.Logger:
    """Returns the module logger."""
    return logging.getLogger(__name__)


def create_device(_worker: Worker, serial: str) -> Device:
    return Device.from_serial(serial)


def get_all_attached_devices(workqueue: WorkQueue) -> List[Device]:
    """Returns a list of all connected devices."""
    if shutil.which("adb") is None:
        raise RuntimeError("Could not find adb.")

    # We could get the device name from `adb devices -l`, but we need to
    # getprop to find other details anyway, and older devices don't report
    # their names properly (nakasi on android-16, for example).
    p = subprocess.run(
        ["adb", "devices"], check=True, stdout=subprocess.PIPE, encoding="utf-8"
    )
    if p.returncode != 0:
        raise RuntimeError("Failed to get list of devices from adb.")

    # The first line of `adb devices` just says "List of attached devices", so
    # skip that.
    for line in p.stdout.split("\n")[1:]:
        if not line.strip():
            continue

        serial, _ = re.split(r"\s+", line, maxsplit=1)

        if "offline" in line:
            logger().info("Ignoring offline device: %s", serial)
            continue
        if "unauthorized" in line:
            logger().info("Ignoring unauthorized device: %s", serial)
            continue

        # Caching all the device details via getprop can actually take quite a
        # bit of time. Do it in parallel to minimize the cost.
        workqueue.add_task(create_device, serial)

    devices = []
    while not workqueue.finished():
        device = workqueue.get_result()
        logger().info("Found device %s", device)
        devices.append(device)

    return devices


def exclude_device(device: Device) -> bool:
    """Returns True if a device should be excluded from the fleet."""
    exclusion_list_env = os.getenv("NDK_DEVICE_EXCLUSION_LIST")
    if exclusion_list_env is None:
        return False
    exclusion_list = Path(exclusion_list_env).read_text(encoding="utf-8").splitlines()
    return device.serial in exclusion_list


def find_devices(
    sought_devices: Dict[int, List[Abi]], workqueue: WorkQueue
) -> DeviceFleet:
    """Detects connected devices and returns a set for testing.

    We get a list of devices by scanning the output of `adb devices` and
    matching that with the list of desired test configurations specified by
    `sought_devices`.
    """
    fleet = DeviceFleet(sought_devices)
    for device in get_all_attached_devices(workqueue):
        if not exclude_device(device):
            fleet.add_device(device)

    return fleet
