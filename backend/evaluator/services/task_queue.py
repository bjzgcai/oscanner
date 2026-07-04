"""In-process queue for expensive evaluator analysis jobs."""

from __future__ import annotations

import asyncio
import inspect
import os
from collections import deque
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Deque, Optional, Union

ProgressCallback = Callable[[str], Union[object, Awaitable[object]]]


class EvaluatorQueueFull(RuntimeError):
    """Raised when no more pending evaluator jobs can be accepted."""


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, value)


class EvaluatorQueue:
    """Small FIFO queue that limits concurrent expensive evaluator jobs."""

    def __init__(self, *, max_concurrent: int = 1, max_pending: int = 100):
        self.max_concurrent = max(1, int(max_concurrent))
        self.max_pending = max(0, int(max_pending))
        self._running = 0
        self._pending: Deque[object] = deque()
        self._condition = asyncio.Condition()

    def snapshot(self) -> dict[str, int]:
        return {
            "max_concurrent": self.max_concurrent,
            "running": self._running,
            "pending": len(self._pending),
            "max_pending": self.max_pending,
        }

    def _position(self, token: object) -> int:
        try:
            return list(self._pending).index(token) + 1
        except ValueError:
            return 0

    async def _notify(
        self,
        progress_callback: Optional[ProgressCallback],
        message: str,
    ) -> None:
        if progress_callback is None:
            return
        result = progress_callback(message)
        if inspect.isawaitable(result):
            await result

    @asynccontextmanager
    async def acquire(self, progress_callback: Optional[ProgressCallback] = None):
        token = object()
        acquired = False
        queued = False
        last_position = 0

        try:
            async with self._condition:
                must_wait = self._running >= self.max_concurrent or bool(self._pending)
                if must_wait and len(self._pending) >= self.max_pending:
                    raise EvaluatorQueueFull(
                        f"Evaluator queue is full ({self.max_pending} pending request(s))"
                    )

                self._pending.append(token)
                last_position = self._position(token)
                if must_wait:
                    queued = True
                    await self._notify(
                        progress_callback,
                        f"Evaluator is busy; queued request at position {last_position}.",
                    )

                while self._pending[0] is not token or self._running >= self.max_concurrent:
                    await self._condition.wait()
                    position = self._position(token)
                    if queued and position and position != last_position:
                        last_position = position
                        await self._notify(
                            progress_callback,
                            f"Queued request moved to position {position}.",
                        )

                self._pending.popleft()
                self._running += 1
                acquired = True
        except BaseException:
            if not acquired:
                async with self._condition:
                    try:
                        self._pending.remove(token)
                    except ValueError:
                        pass
                    self._condition.notify_all()
            raise

        if queued:
            await self._notify(progress_callback, "Evaluator slot available; starting request.")

        try:
            yield
        finally:
            if acquired:
                async with self._condition:
                    self._running = max(0, self._running - 1)
                    self._condition.notify_all()


evaluator_queue = EvaluatorQueue(
    max_concurrent=_env_int("OSCANNER_EVALUATOR_MAX_CONCURRENT_JOBS", 1, minimum=1),
    max_pending=_env_int("OSCANNER_EVALUATOR_MAX_PENDING_JOBS", 100, minimum=0),
)
