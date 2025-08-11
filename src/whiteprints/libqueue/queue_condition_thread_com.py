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
from typing import (
    Final,
    Literal,
    override,
)

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libqueue.queue_exceptions import NotOwningError
from whiteprints.libqueue.queue_interface import (
    LockLike,
    QueueCommunicationBackend,
    QueueLockBackend,
)


__all__: Final = [
    "ThreadConditionCommunication",
    "ThreadLockBackend",
]
"""Public module attributes."""


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
        size: Callable[[], int] | None = None,
        *,
        queue_reentrant_lock: bool = True,
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
            self.create_rlock()
            if queue_reentrant_lock
            else
            self.create_lock()
        )
        if size is None:
            self.init_semaphores(max_slots)
        else:
            self.init_conditions(max_slots, size)

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

    def init_semaphores(self, max_slots: int | None) -> None:
        """Build semaphore-based signaling for queues without size predicate.

        Sets up cross contexts for producer/consumer coordination using
        semaphores. For unbounded queues, a no-op semaphore is used for slots
        and items so that capacity checks become trivial.

        Args:
            max_slots: Queue capacity. ``None`` means unbounded.

        Side Effects:
            Initializes ``not_empty`` and ``not_full`` cross contexts.
        """
        threading = import_lazy("threading")
        cross_context = import_lazy_project("libqueue.queue_cross_context")
        slots = (
            cross_context.NoSemaphore()
            if max_slots is None
            else
            threading.BoundedSemaphore(max_slots)
        )
        items = cross_context.NoSemaphore()

        self.not_empty = import_lazy_project(
            "libqueue.queue_cross_context"
        ).CrossSemaphoreContext(
            acquire=items,
            release=slots,
            rollback_on_error=True,
        )
        self.not_full = (
            import_lazy_project(
                "libqueue.queue_cross_context"
            ).CrossSemaphoreContext(
                acquire=slots,
                release=items,
                rollback_on_error=False,
            )
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
        slots = (
            import_lazy_project(
                "libqueue.queue_cross_context"
            ).TrueCondition(self.queue_lock)
            if max_slots is None
            else
            threading.Condition(self.queue_lock)
        )
        items = (
            threading.Condition(self.queue_lock)
        )

        self.not_empty = import_lazy_project(
            "libqueue.queue_cross_context"
        ).CrossConditionContext(
            acquire=items,
            release=slots,
            predicate=lambda: size() < 1,
            rollback_on_error=True,
        )
        self.not_full = (
            import_lazy_project(
                "libqueue.queue_cross_context"
            ).CrossConditionContext(
                acquire=slots,
                release=items,
                predicate=(
                    (lambda: False)
                    if max_slots is None
                    else
                    (lambda: size() >= max_slots)
                ),
                rollback_on_error=False,
            )
        )


class ThreadConditionCommunication[U](QueueCommunicationBackend[U]):
    """Thread-based in-memory queue using deque or SimpleQueue.

    Wraps a collections.deque or queue.SimpleQueue with thread
    synchronization via ThreadLockBackend. The deque path uses a size
    predicate and conditions for bounded/unbounded queues. The SimpleQueue
    path uses semaphores for bounded capacity. Not safe for cross-process
    use; intended for thread-local backends only.
    """

    __slots__ = (
        "get",
        "locks",
        "max_slots",
        "owner_tid",
        "put",
    )

    @override
    def __init__(
        self,
        max_slots: int | None,
        backend: Literal["condition", "semaphore"] = "semaphore",
        *,
        queue_reentrant_lock: bool = True,
    ) -> None:
        """Initialize the thread communication backend.

        Chooses between a deque-based path (with a size predicate and
        conditions) and a SimpleQueue-based path (semaphore-backed, no size
        predicate). Ownership is recorded using the current native thread id.

        Args:
            max_slots: Queue capacity. ``None`` means unbounded.
            backend: Either ``"condition"`` for deque or ``"semaphore"`` for
                SimpleQueue.
            queue_reentrant_lock: If True, use an RLock for the queue lock;
                else a regular Lock.
        """
        self.max_slots = max_slots
        self.owner_tid = import_lazy("threading").get_native_id()

        match backend:
            case "semaphore":
                queue = import_lazy("queue").SimpleQueue()
                self.put = queue.put
                self.get = queue.get
                self.locks = ThreadLockBackend(
                    max_slots,
                    queue_reentrant_lock=queue_reentrant_lock,
                )
            case _:
                queue = import_lazy("collections").deque[U]()
                self.put = queue.append
                self.get = queue.popleft
                self.locks = ThreadLockBackend(
                    self.max_slots,
                    queue.__len__,
                    queue_reentrant_lock=queue_reentrant_lock,
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
