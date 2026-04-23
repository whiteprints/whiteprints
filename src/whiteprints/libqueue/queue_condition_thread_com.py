# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue protocol definitions and core error types.

This module defines the foundational protocols and exceptions used by
the Whiteprints queue system. It provides a backend-agnostic interface
for synchronous and asynchronous queues, along with lifecycle and status
management.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from functools import partial
from types import TracebackType
from typing import (
    Final,
    Literal,
    final,
    override,
)

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libqueue.queue_exceptions import NotOwningError, ShutDownError
from whiteprints.libqueue.queue_interface import (
    ConditionLike,
    LockLike,
    QueueCommunicationBackend,
    QueueLockBackend,
    SemaphoreLike,
)


__all__: Final = [
    "ThreadConditionCommunication",
    "ThreadLockBackend",
]
"""Public module attributes."""


@final
class CapacityGate(SemaphoreLike):
    __slots__ = (
        "_cond",
        "_monotonic",
        "_notify",
        "_size",
        "_value",
        "_wait",
        "_waiters",
        "transient_overshoot",
    )

    @override
    def __init__(
        self,
        value: int,
        size: Callable[[], int],
        lock: LockLike | None = None,
        *,
        transient_overshoot: bool = False,
    ) -> None:
        self._cond = import_lazy("threading").Condition(
            lock or import_lazy("threading").Lock()
        )
        self._wait = self._cond.wait
        self._notify = self._cond.notify
        self._value = value
        self._size = size
        self._monotonic = import_lazy("time").monotonic
        self._waiters = 0
        self.transient_overshoot = transient_overshoot

    def _wait_capacity(
        self,
        size: Callable[[], int],
        value: int,
        wait: Callable[[], None],
    ) -> bool:
        if size() < value:
            return True
        self._waiters += 1
        try:
            while size() >= value:
                wait()
        finally:
            self._waiters -= 1
        return True

    def _wait_capacity_timeout(
        self,
        size: Callable[[], int],
        value: int,
        wait: Callable[[float], None],
        timeout: float,
        monotonic: Callable[[], int],
    ) -> bool:
        if size() < value:
            return True
        end = monotonic() + timeout
        self._waiters += 1
        try:
            while size() >= value:
                if (rem := end - monotonic()) <= 0:
                    return False
                wait(rem)
        finally:
            self._waiters -= 1
        return True

    @override
    def acquire(
        self, blocking: bool = True, timeout: float | None = None
    ) -> bool:
        size = self._size
        value = self._value
        if blocking:
            if self.transient_overshoot and size() < value:
                return True

            wait = self._wait
            if timeout is None:
                with self._cond:
                    return self._wait_capacity(size, value, wait)

            monotonic = self._monotonic
            with self._cond:
                return self._wait_capacity_timeout(
                    size, value, wait, timeout, monotonic
                )

        # Non-blocking
        with self._cond:
            return size() < value

    __enter__ = acquire

    @override
    def release(self, n: int = 1) -> None:
        if self._waiters <= 0:
            return
        with self._cond:
            if waiters := self._waiters:
                self._notify(min(waiters, n))
        return

    @override
    def __exit__(
        self,
        /,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


class ThreadLockBackend(QueueLockBackend):
    """Thread-based lock and condition/semaphore coordination.

    Manages locks and condition or semaphore contexts for queue backends.
    If a size callback is given, uses condition variables to signal empty
    or full states. Without size, uses semaphores for capacity control. The
    chosen mode depends on backend type and whether the queue is bounded.
    """

    __slots__ = (
        "not_empty",
        "not_full",
        "owner_lock",
        "queue_lock",
    )

    @override
    def __init__(
        self,
        max_slots: int | None,
        size: Callable[[], int],
        *,
        queue_reentrant_lock: bool = False,
    ) -> None:
        """Initialize locks and signaling for a thread queue.

        Chooses signaling strategy based on whether a size predicate is
        supplied. If ``size`` is provided, condition variables are used.
        Otherwise, a semaphore-based setup is created. Unbounded queues use
        no-op primitives where capacity does not apply.

        Args:
            max_slots: Queue capacity. ``None`` means unbounded.
            size: Callable returning the current queue length for condition
                mode.
            queue_reentrant_lock: If True, use an RLock for the queue lock;
                else a regular Lock.
        """
        self.owner_lock = self.create_rlock()
        self.queue_lock = (
            self.create_rlock() if queue_reentrant_lock else self.create_lock()
        )
        #  if size is None:
        #      self.init_semaphores(max_slots)
        #  else:
        #      self.init_conditions(max_slots, size)
        self.init_semaphores(max_slots, size)

    @override
    def create_lock(self) -> LockLike:
        """Create a standard (non-reentrant) lock.

        Returns:
            A lock-like object suitable for mutual exclusion.
        """
        return import_lazy("threading").Lock()

    @override
    def create_rlock(self) -> LockLike:
        """Create a reentrant lock.

        Returns:
            A lock-like object that can be acquired repeatedly by the same
            thread.
        """
        return import_lazy("threading").RLock()

    def init_semaphores(
        self,
        max_slots: int | None,
        size: Callable[[], int],
    ) -> None:
        """Build semaphore-based signaling for queues without size predicate.

        Sets up cross contexts for producer/consumer coordination using
        semaphores. For unbounded queues, a no-op semaphore is used for slots
        and items so that capacity checks become trivial.

        Args:
            max_slots: Queue capacity. ``None`` means unbounded.

        Side Effects:
            Initializes ``not_empty`` and ``not_full`` cross contexts.
        """
        cross_context = import_lazy_project("libqueue.queue_cross_context")
        if max_slots is None:
            slots = cross_context.NoSemaphore()
        elif max_slots == 1:
            slots = self.queue_lock
        else:
            slots = CapacityGate(max_slots, size, self.queue_lock)

        items = cross_context.NoSemaphore()

        self.not_empty = cross_context.CrossSemaphoreContext(
            acquire=items,
            release=slots,
        )
        self.not_full = cross_context.CrossSemaphoreContext(
            acquire=slots,
            release=items,
        )

    def init_conditions(
        self,
        max_slots: int | None,
        size: Callable[[], int],
    ) -> None:
        """Build condition-based signaling using the queue lock.

        Creates two condition variables guarded by ``queue_lock``. For
        unbounded queues, a TrueCondition is used for slots and the "full"
        predicate is permanently false. ``not_empty`` waits while the queue is
        empty based on ``size()``.

        Args:
            max_slots: Queue capacity. ``None`` means unbounded.
            size: Callable returning the current queue length.

        Side Effects:
            Initializes ``not_empty`` and ``not_full`` cross contexts.
        """
        threading = import_lazy("threading")
        cross_context = import_lazy_project("libqueue.queue_cross_context")
        slots = (
            cross_context.TrueCondition(self.queue_lock)
            if max_slots is None
            else threading.Condition(self.queue_lock)
        )
        items = threading.Condition(self.queue_lock)

        self.not_empty = cross_context.CrossConditionContext(
            acquire=items,
            release=slots,
            predicate=lambda: size() < 1,
        )
        self.not_full = cross_context.CrossConditionContext(
            acquire=slots,
            release=items,
            predicate=(
                (lambda: False)
                if max_slots is None
                else (lambda: size() >= max_slots)
            ),
        )


class ThreadCounter(AbstractContextManager[None]):
    @override
    def __init__(
        self,
        thread_ids: list[int],
        null: ConditionLike,
        can_start: ConditionLike,
        receivers: list[int],
        *,
        is_receiver: bool,
    ) -> None:
        super().__init__()
        self.thread_ids = thread_ids
        self.null = null
        self.can_start = can_start
        self.receivers = receivers
        self.is_receiver = is_receiver

    @override
    def __enter__(self) -> None:
        if not self.is_receiver:
            while len(self.receivers) < 1:
                with self.can_start:
                    self.can_start.wait_for(
                        lambda: len(self.receivers) > 0,
                        None,
                    )

        with self.null:
            self.thread_ids.append(import_lazy("threading").get_native_id())
            if self.is_receiver and len(self.thread_ids) == 1:
                self.can_start.notify_all()

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool:
        with self.null:
            self.thread_ids.remove(import_lazy("threading").get_native_id())
            if len(self.thread_ids) < 1:
                self.null.notify_all()

        return isinstance(exc_value, ShutDownError)


class ThreadConditionCommunication[U](QueueCommunicationBackend[U]):
    """Thread-based in-memory queue using deque or SimpleQueue.

    Wraps a collections.deque or queue.SimpleQueue with thread
    synchronization via ThreadLockBackend. The deque path uses a size
    predicate and conditions for bounded/unbounded queues. The SimpleQueue
    path uses semaphores for bounded capacity. Not safe for cross-process
    use; intended for thread-local backends only.
    """

    __slots__ = (
        "backend",
        "get",
        "locks",
        "max_slots",
        "owner_tid",
        "put",
        "queue_reentrant_lock",
    )

    @override
    def __init__(
        self,
        backend: Literal["condition", "semaphore"] = "semaphore",
        *,
        queue_reentrant_lock: bool = False,
    ) -> None:
        """Initialize the thread communication backend.

        Chooses between a deque-based path (with a size predicate and
        conditions) and a SimpleQueue-based path (semaphore-backed, no size
        predicate). Ownership is recorded using the current native thread id.

        Args:
            backend: Either ``"condition"`` for deque or ``"semaphore"`` for
                SimpleQueue.
            queue_reentrant_lock: If True, use an RLock for the queue lock;
                else a regular Lock.
        """
        self.backend = backend
        self.queue_reentrant_lock = queue_reentrant_lock
        self.owner_tid = import_lazy("threading").get_native_id()

    def producer(self) -> AbstractContextManager[None]:
        return ThreadCounter(
            self.producers,
            self.producer_null,
            self.has_receivers,
            self.receivers,
            is_receiver=False,
        )

    def receiver(self) -> AbstractContextManager[None]:
        return ThreadCounter(
            self.receivers,
            self.receiver_null,
            self.has_receivers,
            self.receivers,
            is_receiver=True,
        )

    def wait_no_producers(self) -> bool:
        with self.producer_null:
            return self.producer_null.wait_for(lambda: len(self.producers) < 1)

    def wait_no_receivers(self) -> bool:
        with self.receiver_null:
            return self.receiver_null.wait_for(lambda: len(self.receivers) < 1)

    def process_error(self, base_error: BaseException) -> BaseException:
        queue = import_lazy("queue")
        if isinstance(base_error, queue.Empty):
            return import_lazy_project(
                "libqueue.queue_exceptions"
            ).EmptyError()

        if isinstance(base_error, queue.Full):
            return import_lazy_project("libqueue.queue_exceptions").FullError()

        return base_error

    @override
    def bind_methods(
        self,
        max_slots: int | None,
        *,
        put_block: bool,
        put_timeout: float | None,
        get_block: bool,
        get_timeout: float | None,
    ) -> None:
        match self.backend:
            case "semaphore":
                queue = import_lazy("queue").SimpleQueue()
                self.put = queue.put
                if not get_block:
                    self.get = queue.get_nowait
                elif get_timeout is None:
                    self.get = queue.get
                elif get_timeout > 0:
                    self.get = partial(queue.get, True, get_timeout)
                else:
                    self.get = queue.get_nowait

                self.locks = ThreadLockBackend(
                    max_slots,
                    queue.qsize,
                    queue_reentrant_lock=self.queue_reentrant_lock,
                )
            case _:
                queue = import_lazy("collections").deque[U]()
                self.put = queue.append
                self.get = queue.popleft
                self.locks = ThreadLockBackend(
                    max_slots,
                    queue.__len__,
                    queue_reentrant_lock=self.queue_reentrant_lock,
                )

        self.receivers: list[int] = []
        self.receiver_null = import_lazy("threading").Condition(
            self.locks.owner_lock,
        )

        self.producers: list[int] = []
        self.producer_null = import_lazy("threading").Condition(
            self.locks.owner_lock,
        )

        self.has_receivers = import_lazy("threading").Condition(
            self.locks.owner_lock
        )

    @property
    @override
    def owning(self) -> bool:
        """True if the current thread owns this queue.

        Ownership is the thread that constructed the instance, tracked by
        native thread id. The check is performed under ``owner_lock`` for
        safety.
        """
        current_tid = import_lazy("threading").get_native_id()
        with self.locks.owner_lock:
            return current_tid == self.owner_tid

    @override
    def transfer_ownership(self) -> None:
        """Transfer ownership to the current thread.

        Updates the stored native thread id under ``owner_lock`` so subsequent
        owner-only operations are permitted for this thread.
        """
        current_tid = import_lazy("threading").get_native_id()
        with self.locks.owner_lock:
            self.owner_tid = current_tid

    @override
    def revoke_ownership(self) -> None:
        """Revoke ownership so no thread is considered the owner.

        After revocation, owner-only operations such as ``shutdown()`` will
        raise ``NotOwningError`` until ownership is transferred again.
        """
        with self.locks.owner_lock:
            self.owner_tid = -1

    @override
    def shutdown(self) -> None:
        """Shutdown the backend if the caller owns the queue.

        Performs an ownership check and raises if violated. This backend does
        not manage additional resources here; higher layers may extend
        shutdown.

        Raises:
            NotOwningError: If the caller thread is not the owner.
        """
        if not self.owning:
            raise NotOwningError

        with self.locks.owner_lock:
            self.producer_null.notify_all()
            self.receiver_null.notify_all()
            self.has_receivers.notify_all()
