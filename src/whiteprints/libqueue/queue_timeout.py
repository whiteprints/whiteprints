# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Locking utilities for coordinated timeouts.

This module provides utility constructs for managing pairs of lock-like
objects (typically a lock and an optional semaphore) under coordinated
timeout and blocking semantics. It allows acquiring both with shared
timeout logic and clean release on failure or exit.

Used internally by Whiteprints' concurrency mechanisms to safely control
queue-like access patterns.
"""

from contextlib import AbstractContextManager
from functools import cached_property
from types import ModuleType, TracebackType
from typing import (
    Final,
    override,
)

from whiteprints.lazy_import import import_lazy
from whiteprints.libqueue.queue_protocol import LockLike


__all__: Final = ["TimeoutPair"]
"""Public module attributes."""


class TimeoutPair[LockT: LockLike, SemT: LockLike](
    AbstractContextManager[tuple[LockT, SemT | None]]
):
    """Context manager that acquires two locks under a shared timeout.

    This utility coordinates the timed acquisition of two lock-like
    resources: a primary `lock` and an optional `sem`. It attempts to
    acquire both in order, sharing the same timeout constraint across both.

    On failure or exception, any already-acquired resource is cleanly
    released to prevent deadlocks.

    Attributes:
        lock: The main lock-like object.
        sem: An optional secondary lock/semaphore.
        timeout: The shared timeout for both acquisitions, in seconds.
    """

    def __init__(
        self,
        lock: LockT,
        sem: SemT | None = None,
        *,
        timeout: float | None = None,
    ) -> None:
        """Initializes a coordinated lock + semaphore pair.

        Args:
            lock: The primary lock-like resource.
            sem: An optional semaphore or secondary lock-like object.
            timeout: Optional timeout applied across both acquisitions.
        """
        self.lock = lock
        self.sem = sem
        self.timeout = timeout

    @cached_property
    def _time(self) -> ModuleType:
        """Lazily imports the `time` module for monotonic clock access."""
        return import_lazy("time")

    def _acquire_sem_with_timeout(self, deadline: float | None) -> bool:
        """Attempts to acquire the semaphore within the shared deadline.

        Args:
            deadline: Absolute time (from `monotonic()`) by which the sem
                must be acquired, or None to block indefinitely.

        Returns:
            True if the semaphore was acquired, False otherwise.
        """
        if self.sem is None:
            return True

        if deadline is None:
            self.sem.acquire()
            return True

        remaining = deadline - self._time.monotonic()
        return remaining > 0 and self.sem.acquire(timeout=remaining)

    def _acquire_lock_with_timeout(self, deadline: float | None) -> bool:
        """Attempts to acquire the main lock within the shared deadline.

        Args:
            deadline: Absolute time (from `monotonic()`) for acquisition.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        if deadline is None:
            self.lock.acquire(block=True)
            return True

        remaining = deadline - self._time.monotonic()
        return remaining > 0 and self.lock.acquire(
            block=True, timeout=remaining
        )

    def safe_sem_release(self) -> None:
        """Releases the semaphore only if it exists.

        This is used to safely unwind partial acquisitions.
        """
        if self.sem is not None:
            self.sem.release()

    @override
    def __enter__(self) -> tuple[LockT, SemT | None]:
        """Acquires both the semaphore and the lock under a shared timeout.

        Raises:
            TimeoutError: If either acquisition fails before the timeout.

        Returns:
            A tuple of (lock, sem) — where `sem` may be None.
        """
        deadline = (
            None
            if self.timeout is None
            else self._time.monotonic() + self.timeout
        )

        if not self._acquire_sem_with_timeout(deadline):
            raise TimeoutError

        try:
            if not self._acquire_lock_with_timeout(deadline):
                self.safe_sem_release()
                raise TimeoutError
        except:
            self.safe_sem_release()
            raise

        return self.lock, self.sem

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Releases the lock and semaphore on context exit.

        This ensures that both the primary lock and optional semaphore
        are released when the context manager exits, regardless of whether
        an exception occurred.

        Args:
            exc_type: Exception type, if raised.
            exc_val: Exception instance, if raised.
            exc_tb: Traceback, if raised.
        """
        self.lock.release()
        self.safe_sem_release()
