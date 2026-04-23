# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Unified queue interface that delegates to thread or process backends.

This module provides a high-level `Queue` class that wraps an underlying
`QueueBackend` implementation. It abstracts away the details of whether the
queue operates in a thread-based or process-based environment.

The backend is chosen based on the provided arguments:

- If `backend` is given explicitly, it is used directly.
- If a `multiprocessing` context (`ctx`) is provided, a `ProcessBackend` is
  instantiated using that context.
- Otherwise, a `ThreadBackend` is used by default.

This allows a single `Queue` API to be used across concurrency models,
facilitating flexible, testable, and portable task queuing patterns.
"""

from multiprocessing.context import BaseContext
from typing import Self, override

from whiteprints.lazy_import import import_lazy_project
from whiteprints.libqueue.queue_hook import NoQueueHook, QueueHookBase
from whiteprints.libqueue.queue_protocol import (
    LockLike,
    QueueBackend,
    Sentinel,
)


class Queue[T, U, R](QueueBackend[T, U, R]):
    """High-level queue proxy that delegates to a thread or process backend.

    This class abstracts the backend implementation behind a unified
    QueueBackend interface. It selects the appropriate backend based on the
    context provided or defaults to a thread-safe implementation.
    """

    @override
    def __init__(
        self,
        maxsize: int = 0,
        hooks: type[QueueHookBase[Self, T, U, R]] = NoQueueHook,
        backend: QueueBackend[T, U, R] | None = None,
        ctx: BaseContext | None = None,
    ) -> None:
        if backend is not None:
            self._queue = backend

        elif ctx is not None:
            self._queue = import_lazy_project(
                "libqueue.queue_process"
            ).ProcessBackend[T](maxsize, hooks, ctx=ctx)
        else:
            self._queue = import_lazy_project(
                "libqueue.queue_thread"
            ).ThreadBackend[T](maxsize, hooks)

    @property
    def backend(self) -> QueueBackend[T, U, R]:
        """Returns the underlying backend instance (thread or process)."""
        return self._queue

    @override
    def put(self, item: T | Sentinel, *, timeout: float | None = None) -> None:
        self._queue.put(item, timeout=timeout)

    @override
    def get(
        self,
        *,
        timeout: float | None = None,
    ) -> R:
        return self._queue.get(timeout=timeout)

    @property
    @override
    def size(self) -> int:
        return self._queue.size

    @override
    def qsize_lock(self) -> LockLike:
        return self._queue.qsize_lock()

    @property
    @override
    def is_shutdown(self) -> bool:
        return self._queue.is_shutdown

    @property
    @override
    def owning(self) -> bool:
        return self._queue.owning

    @override
    def transfer_ownership(self) -> None:
        return self._queue.transfer_ownership()

    @override
    def revoke_ownership(self) -> None:
        return self._queue.revoke_ownership()

    @override
    def shutdown(self) -> None:
        self._queue.shutdown()
