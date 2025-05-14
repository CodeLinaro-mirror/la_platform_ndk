# Copyright (C) 2025 The Android Open Source Project
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import multiprocessing
from asyncio import Queue
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class BuildTaskLimiter:
    def __init__(self, queue: Queue[None]) -> None:
        self.queue = queue

    @staticmethod
    async def create(
        max_concurrent_jobs: int = multiprocessing.cpu_count(),
    ) -> BuildTaskLimiter:
        queue: Queue[None] = Queue()
        for _ in range(max_concurrent_jobs):
            await queue.put(None)
        return BuildTaskLimiter(queue)

    @asynccontextmanager
    async def rate_limited(self) -> AsyncIterator[None]:
        await self.queue.get()
        try:
            yield
        finally:
            await self.queue.put(None)
