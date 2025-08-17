# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue protocol definitions and core error types.

This module defines the foundational protocols and exceptions used by
the Whiteprints queue system. It provides a backend-agnostic interface
for synchronous and asynchronous queues, along with lifecycle and status
management.
"""

from collections.abc import (
    Callable,
    Iterator,
    Mapping,
)
from contextlib import AbstractContextManager
from types import TracebackType
from typing import (
    Any,
    Final,
    Self,
    override,
)

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libqueue import SHUTDOWN
from whiteprints.libqueue.queue_exceptions import (
    QueueError,
    ShutDownError,
)
from whiteprints.libqueue.queue_hook import NoQueueHook, QueueHook
from whiteprints.libqueue.queue_interface import (
    QueueCommunicationBackend,
    QueueInterface,
    QueueLifecycle,
    QueueLockBackend,
    QueueStatus,
    QueueSyncOps,
)


__all__: Final = [
    "QueueBackend",
]
"""Public module attributes."""


class QueueSyncOpsBase[T, U, R](QueueSyncOps[T, U, R]):
    """Synchronous queue interface with lifecycle-aware instrumentation hooks.

    This protocol defines a generic, synchronous (blocking-compatible) queue
    interface that supports:

        - `put()` for enqueuing items
        - `get()` for dequeuing items
        - `shutdown()` for graceful shutdown signaling

    It also supports instrumentation via a single `QueueHookBase` instance,
    typically injected via a hook class type and bound to the queue at
    instantiation.

    Generics:
        T: Input item type for put().
        U: Internal stored type (after pre-processing).
        R: Output item type for get().

    These allow hooks to transform or instrument queue items as they enter and
    leave. For a simple queue, T = U = R.

    Attributes:
        hooks: A concrete `QueueHookBase` instance used for instrumentation.
            Automatically initialized from the given hook class type.

    Notes:
        - Hook callbacks run **outside internal queue locks**.
        - Hook callbacks run **only after successful queue operations**.
        - Hook context managers wrap queue lifecycle phases (`put`, `get`,
        etc.).
    """

    @override
    def __init__(
        self,
        max_slots: int | None,
        hooks: QueueHook[T, U, R] | None = None,
        com: QueueCommunicationBackend[U] | None = None,
        *,
        put_block: bool = True,
        put_timeout: float | None = None,
        get_block: bool = True,
        get_timeout: float | None = None,
    ) -> None:
        """Initializes the queue and attaches the given hook type.

        The hook is a class implementing `QueueHookBase`, instantiated
        with a reference to this queue. The resulting instance is used
        to observe or mutate lifecycle events such as put(), get(),
        shutdown(), and task tracking.

        Args:
            hooks: A `QueueHookBase` class or factory function.
                You may pass a hook class (e.g., `LoggingHook`) or a factory
                like `lambda q: LoggingHook(q, arg)` to inject parameters.
            com: Implementation of the communication protocol.
        """
        self.max_slots = max_slots
        self.hooks = hooks or NoQueueHook[T, U, R]()
        self.com = com_ = (
            com
            or import_lazy_project(
                "libqueue.queue_condition_thread_com"
            ).ThreadConditionCommunication[U]()
        )
        com_.bind_methods(
            max_slots=max_slots,
            put_block=put_block,
            put_timeout=put_timeout,
            get_block=get_block,
            get_timeout=get_timeout,
        )
        self._locks = com_.locks

    @property
    @override
    def locks(self) -> QueueLockBackend:
        return self._locks

    @override
    def __iter__(self) -> Iterator[R]:
        """Iterates over items in the queue until shutdown.

        Yields:
            Items from the queue.

        Stops:
            When a ShutDownError is raised.
        """
        while True:
            try:
                yield self.get()
            except ShutDownError:
                break

    def dispatch[K](
        self,
        *,
        dispatcher: Callable[[R], K],
        queue_sinks: Mapping[K, Any],
        drop_on_error: bool = False,
    ) -> K:
        """Dispatches a single item to target queues based on a filter.

        Pulls one item from `self`, uses `dispatcher(item)` to determine its
        destination, and puts it into the appropriate sink from `queue_sinks`.

        This method helps enforce a design where each queue has exactly one
        receiving sink (or listener). That pattern reduces coordination
        complexity and avoids ambiguity in routing and shutdown logic.

        Raises:
            KeyError:if the dispatcher returns a key not in `queue_sinks` and
                `drop_on_error` is False.

        Returns:
            the sink name.
        """
        item = self.get()
        sink_name = dispatcher(item)
        sink = queue_sinks.get(sink_name)
        if sink is None and not drop_on_error:
            raise KeyError(sink_name)

        if sink is not None:
            sink.put(item)

        return sink_name


class QueueLifecycleBase[T, U, R](QueueLifecycle[T, U, R]):
    """Queue interface for shutdown, task tracking, and cleanup.

    This protocol defines lifecycle-related methods that govern the state
    of the queue. It includes shutdown control, task tracking, and context
    manager support for automatic resource cleanup.

    This interface builds on QueueSyncOps and assumes the presence of a
    shutdown-aware backend.
    """

    @override
    def __init__(self) -> None:
        self.finalizer = import_lazy("weakref").finalize(
            self, self._finalize_queue
        )

    def producer(self) -> AbstractContextManager[None]:
        if (com := getattr(self, "com", None)) is None:
            raise ShutDownError

        return com.producer()

    def receiver(self) -> AbstractContextManager[None]:
        if (com := getattr(self, "com", None)) is None:
            raise ShutDownError

        return com.receiver()

    @property
    @override
    def owning(self) -> bool:
        with self.locks.owner_lock:
            return self.com is not None and self.com.owning

    def _finalize_queue(self) -> None:
        """Best effort shutdown of the queue.

        This method is called when the queue object is about to be destroyed.
        If the current thread is marked as the queue's owner (see `owning`),
        it will attempt to call `shutdown()` in order to release system
        resources such as locks, pipes, and threads.

        Warning:
            If a worker thread receives the queue but does **not** override the
            default `owning=True` (e.g., by passing it from the main thread
            without any context adaptation), and that thread is
            garbage-collected or exits abnormally, the queue may **shut down
            prematurely**.

            This can trigger a **system-wide shutdown signal** and affect other
            active producers or consumers still using the queue.

        To prevent this:
            - Always ensure only the true lifecycle manager owns the queue.
            - Use the `owning` property in your implementation to determine
              whether `shutdown()` should be called.

        Exceptions are suppressed during interpreter teardown to prevent
        cascading errors when modules are partially unloaded.

        Note:
            In production, always prefer explicit `shutdown()` or use `with`
            blocks to manage queue lifecycle explicitly and safely.
        """
        try:
            if self.owning:
                self.shutdown()
        except (AttributeError, OSError, ValueError, QueueError):
            pass

    def send_shutdown(self) -> None:
        """Signals shutdown by inserting a sentinel into the queue.

        This is a convenience wrapper that allows consumers to exit
        cleanly by detecting the sentinel.
        """
        self.put(SHUTDOWN)

    def close(self) -> Self:
        """Shuts down the queue and returns self.

        This is useful in fluent interfaces or when chaining methods.

        Returns:
            self
        """
        self.shutdown()
        return self

    @override
    def __enter__(self) -> None:
        """No-op context manager entry point."""
        return

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Shuts down the queue on context manager exit, if owned.

        This method calls `shutdown()` when the queue context is exited. If the
        current thread is not the queue owner, the shutdown may be skipped or
        raise an error.

        Args:
            exc_type: The exception type, if raised.
            exc_val: The exception instance, if raised.
            exc_tb: The traceback, if raised.
        """
        self.shutdown()


class QueueStatusBase[T, U, R](
    QueueStatus[T, U, R],
    QueueLifecycle[T, U, R],
):
    """Queue interface for monitoring status and capacity.

    This protocol adds inspection methods to the queue lifecycle. It
    provides access to the current size, maximum capacity, and boolean
    status flags for emptiness and fullness.
    """

    def __bool__(self) -> bool:
        """Returns True if the queue is active and not empty.

        Returns:
            True if the queue is not shut down and not empty.
        """
        return not self.is_shutdown


class QueueBackend[T, U, R](
    QueueInterface[T, U, R],
    QueueStatusBase[T, U, R],
    QueueSyncOpsBase[T, U, R],
    QueueLifecycleBase[T, U, R],
):
    """Full backend interface for Whiteprints queues.

    This protocol represents a complete, usable queue backend. It includes
    synchronous and asynchronous operations, lifecycle management, task
    tracking, and queue status inspection.

    A conforming backend must implement all methods and properties defined
    in QueueAsyncOps and QueueStatus.

    This protocol is typically implemented by concrete backends like
    ThreadBackend or ProcessBackend.
    """

    def __init__(
        self,
        max_slots: int | None = None,
        hooks: QueueHook[T, U, R] | None = None,
        com: QueueCommunicationBackend[U] | None = None,
        *,
        put_block: bool = True,
        put_timeout: float | None = None,
        get_block: bool = True,
        get_timeout: float | None = None,
    ) -> None:
        QueueSyncOpsBase[T, U, R].__init__(
            self,
            max_slots,
            hooks,
            com,
            put_block=put_block,
            put_timeout=put_timeout,
            get_block=get_block,
            get_timeout=get_timeout,
        )
        QueueLifecycleBase[T, U, R].__init__(self)
