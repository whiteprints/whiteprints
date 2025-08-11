# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Condition based implementation of the Whiteprints queue backend.

In-memory queue implementation compatible with the QueueBackend protocol.
It uses condition variables for blocking behavior and supports graceful
shutdown with sentinel-based signaling.

The implementation ensure shutdown and predictable task completion.
"""

from collections.abc import Container
from contextlib import AbstractContextManager
from textwrap import dedent, indent
from types import FunctionType, TracebackType
from typing import (
    ClassVar,
    Final,
    Protocol,
    TypedDict,
    override,
    runtime_checkable,
)

from whiteprints.lazy_import import import_lazy
from whiteprints.libqueue import (
    SHUTDOWN,
    BaseSentinel,
    is_noop,
)
from whiteprints.libqueue.queue_base import QueueBackend
from whiteprints.libqueue.queue_exceptions import (
    EmptyError,
    FullError,
    NotOwningError,
    ShutDownError,
    TaskDoneOverflowError,
)
from whiteprints.libqueue.queue_hook import (
    BaseQueueHook,
    QueueHook,
)
from whiteprints.libqueue.queue_interface import (
    ConditionLike,
    LockLike,
    QueueCommunicationBackend,
    QueueInterface,
)


__all__: Final = ["ConditionQueue"]
"""Public module attributes."""

_PUT_SRC_TEMPLATE = dedent("""
    def put[T](self, item: T) -> None:{prepare_put}
        {not_full_acquire}
        try:{inlock_pre_put}
            self._put(item)
        except BaseException as error:
            if not self._not_full_exit_except(
                type(error), error, error.__traceback__
            ):
                raise
        {not_full_release}
""")

_GET_SRC_TEMPLATE = dedent("""
    def get[R](self) -> R:{prepare_get}
        {not_empty_acquire}
        try:{inlock_pre_get}
            {sentinel_get}
        except BaseException as error:
            if not self._not_empty_exit_except(
                type(error), error, error.__traceback__
            ):
                raise
        {not_empty_release}
        return item
""")


class _ConditionQueueState[T, U, R](TypedDict):
    """Serialized internal state of a ConditionQueue instance.

    This TypedDict is used to capture and restore queue state across
    serialization boundaries such as `pickle` or inter-process transfer.

    Attributes:
        hooks: Optional hook implementation used for queue instrumentation.
        com: Underlying shared queue object that implements storage,
                      synchronization, and internal queue mechanics.
    """

    hooks: QueueHook[QueueInterface[T, U, R], T, U, R] | None
    com: QueueCommunicationBackend[U] | None


class ConditionQueue[T, U, R](QueueBackend[T, U, R]):
    """Thread-safe queue backend using condition variables.

    Provides a thread-compatible queue with blocking `put()` and `get()`
    using reentrant locks and condition variables. Supports task tracking
    and graceful shutdown using a sentinel.

    This backend does not spawn background threads. It is safe to use in
    multithreaded programs where clean shutdown and deterministic task
    completion are required.

    Instrumentation is supported via `QueueB` subclasses. Hooks
    may inspect, mutate, or log lifecycle events. They are called after
    successful operations and outside internal locks.

    A pluggable `SharedQueue` implementation defines the internal FIFO
    structure. This enables fast switching between in-memory buffers like
    `deque` or `SimpleQueue` without changing the core logic.

    Attributes:
        hooks: Lifecycle instrumentation handler.
       ._not_empty: Condition triggered when the queue becomes non-empty.
       ._not_full: Condition triggered when the queue becomes not full.
        _rlock: Internal lock guarding read shared queue state.
        _wlock: Internal lock guarding write shared queue state.
    """

    hooks: QueueHook[QueueInterface[T, U, R], T, U, R]

    FULL_ERROR: ClassVar[FullError] = FullError()
    EMPTY_ERROR: ClassVar[EmptyError] = EmptyError()

    __slots__ = (
        "_get",
        "_not_empty",
        "_not_empty_acquire",
        "_not_empty_exit_except",
        "_not_empty_exit_noexcept",
        "_not_full",
        "_not_full_acquire",
        "_not_full_exit_except",
        "_not_full_exit_noexcept",
        "_put",
        "_size",
        "com",
        "get",
        "hooks",
        "put",
        "sentinels",
    )

    @override
    def __init__(
        self,
        hooks: QueueHook[QueueInterface[T, U, R], T, U, R] | None = None,
        com: QueueCommunicationBackend[U] | None = None,
        sentinels: (
            BaseSentinel | type[BaseSentinel] | Container[BaseSentinel] | None
        ) = SHUTDOWN,
    ) -> None:
        """Initializes a thread-safe queue backend using condition variables.

        This constructor wires internal logic to an optional SharedQueue
        implementation and prepares hook dispatching logic. It also resolves
        fast-path decisions for `put()` and `get()` based on queue
        configuration.

        Args:
            hooks: Optional queue hook for lifecycle instrumentation and
                mutation.
            com: Optional SharedQueue adapter to supply the internal
                FIFO and synchronization primitives.

        Note:
            Only the thread that creates the queue is allowed to shut it down.
            Ownership can be transferred or revoked using provided methods.
        """
        super().__init__(hooks, com)
        self.sentinels = sentinels
        self._bind_put_get_primitives()
        self._bind_put()
        self._bind_get()
        self.hooks.after_init(self)

    def _bind_put(self) -> None:
        no_prepare_put = is_noop(self.hooks.prepare_put)
        no_inlock_pre_put = is_noop(self.hooks.inlock_pre_put)
        no_inlock_post_put = is_noop(self.hooks.inlock_post_put)
        no_finalize_put = is_noop(self.hooks.finalize_put)
        no_acquire = is_noop(self._not_full_acquire)
        no_release = is_noop(self._not_full_exit_noexcept)

        if (
            no_prepare_put
            and no_inlock_pre_put
            and no_inlock_post_put
            and no_finalize_put
            and no_acquire
            and no_release
        ):
            self.put = self._put
            return

        if no_acquire:
            not_full_acquire = ""
        else:
            not_full_acquire = dedent(
                """
                if not self._not_full_acquire():
                    raise TimeoutError("put timed out")
                """
            )

        if no_release:
            not_full_release = ""
        else:
            not_full_release = dedent(
                """
                else:{inlock_post_put}
                    self._not_full_exit_noexcept(){finalize_put}
                """.format(
                    inlock_post_put=(
                        ""
                        if no_inlock_post_put else
                        "\n"
                        "    item = self.hooks.inlock_post_put(self, item)"
                    ),
                    finalize_put=(
                        ""
                        if no_finalize_put else
                        "\n"
                        "self.hooks.finalize_put(self, item)"
                    )
                )
            )

        put_src = _PUT_SRC_TEMPLATE.format(
            prepare_put=(
                ""
                if no_prepare_put else
                "\n"
                "        item = self.hooks.prepare_put(self, item)"
            ),
            not_full_acquire=indent(not_full_acquire, " " * 4),
            inlock_pre_put=(
                ""
                if no_inlock_pre_put else
                "\n"
                "           item = self.hooks.inlock_pre_put(self, item)"
            ),
            not_full_release=indent(not_full_release, " " * 4),
        )

        local_ns: dict[str, FunctionType] = {}
        exec(put_src, globals(), local_ns)
        self.put = local_ns["put"].__get__(self, self.__class__)

    def _bind_get(self) -> None:
        prepare_get = not is_noop(self.hooks.prepare_get)
        inlock_pre_get = not is_noop(self.hooks.inlock_pre_get)
        inlock_post_get = not is_noop(self.hooks.inlock_post_get)
        finalize_get = not is_noop(self.hooks.finalize_get)
        noop_acquire = is_noop(self._not_empty_acquire)
        noop_release = is_noop(self._not_empty_exit_noexcept)

        if self.sentinels is None:
            if (
                not prepare_get
                and not inlock_pre_get
                and not inlock_post_get
                and not finalize_get
                and noop_acquire
                and noop_release
            ):
                self.get = self._get
                return

            sentinel_get = "item = self._get()"
        elif isinstance(self.sentinels, BaseSentinel):
            sentinel_get = dedent(
                """
                if (item := self._get()) is self.sentinels:
                    raise self.hooks.on_get_sentinel(self, item, None)
                """
            )
        elif isinstance(self.sentinels, type):
            sentinel_get = dedent(
                """
                if isinstance(item := self._get(), self.sentinels):
                    raise self.hooks.on_get_sentinel(self, item, None)
                """
            )
        else:
            sentinel_get = dedent(
                """
                if (item := self._get()) in self.sentinels:
                    raise self.hooks.on_get_sentinel(self, item, None)
                """
            )

        if noop_acquire:
            not_empty_acquire = ""
        else:
            not_empty_acquire = dedent(
                """
                if not self._not_empty_acquire():
                    raise TimeoutError("get timed out")
                """
            )

        if noop_release:
            not_empty_release = ""
        else:
            not_empty_release = dedent(
                """
                else:{inlock_post_get}
                    self._not_empty_exit_noexcept(){finalize_get}
                """.format(
                    inlock_post_get=(
                        "\n"
                        "    item = self.hooks.inlock_post_get(self)"
                        if inlock_post_get else ""
                    ),
                    finalize_get=(
                        "\n"
                        "item = self.hooks.finalize_get(self, item)"
                        if finalize_get else ""
                    )
                )
            )

        get_src = _GET_SRC_TEMPLATE.format(
            prepare_get=(
                "\n            self.hooks.prepare_get(self)"
                if prepare_get else ""
            ),
            not_empty_acquire=indent(not_empty_acquire, " " * 4),
            inlock_pre_get=(
                "\n"
                "           item = self.hooks.inlock_pre_get(self)"
                if inlock_pre_get else ""
            ),
            sentinel_get=indent(sentinel_get, " " * 8),
            not_empty_release=indent(not_empty_release, " " * 4),
        )

        local_ns: dict[str, FunctionType] = {}
        exec(get_src, globals(), local_ns)
        self.get = local_ns["get"].__get__(self, self.__class__)

    def _bind_put_get_primitives(self) -> None:
        if self.com is not None:
            self._put = self.com.put
            self._get = self.com.get

        self._not_full = self.locks.not_full
        self._not_full_acquire = self._not_full.acquire
        self._not_full_exit_noexcept = self._not_full.exit_noexcept
        self._not_full_exit_except = self._not_full.exit_except
        self._not_empty = self.locks.not_empty
        self._not_empty_acquire = self._not_empty.acquire
        self._not_empty_exit_noexcept = self._not_empty.exit_noexcept
        self._not_empty_except = self._not_empty.exit_except

    @property
    def timeout(self) -> float | None:
        """Gets the timeout for blocking operations. -1 if unset."""
        return getattr(self, "_timeout", -1)

    @timeout.setter
    def timeout(self, value: float | None) -> None:
        """Sets the global timeout (seconds) for all blocking operations.

        Updates the internal wait dispatch method for best performance.
        Per-call timeouts are not supported. Use only if really needed.

        Args:
            value: Seconds to block, or None for no timeout.
        """
        self._timeout = value or -1

    @property
    @override
    def is_shutdown(self) -> bool:
        """Indicates whether the queue has been shut down.

        Returns:
            True if shutdown() has been called, False otherwise.
        """
        return self.com is None

    @staticmethod
    def _time() -> float:
        """Returns the current monotonic time in seconds.

        This is used for deadline calculations in timeouts. It avoids issues
        with system clock changes.
        """
        return import_lazy("time").monotonic()

    def _fail_if_shutdown(self) -> None:
        """Raises ShutDownError if the queue has been shut down.

        No-op otherwise.

        Raises:
            ShutDownError: the queue has been shut down.
        """
        if self.com is None:
            raise ShutDownError

    def _fail_if_shutdown_and_empty(self) -> None:
        """Raises ShutDownError if the queue is shut down and empty.

        No-op otherwise.

        Raises:
            ShutDownError: the queue has been shut down.
        """
        if self.com is None and self._size() < 1:
            raise ShutDownError

    @override
    def shutdown(self) -> None:
        """Shuts down the queue and unblocks all waiting threads.

        After shutdown:
            - Further `put()` or `get()` calls will raise `ShutDownError`
            - Blocked consumers will be notified and can exit cleanly
            - Internal resources are marked for cleanup

        Only the thread that created the queue (the owner) is permitted to
        call this method. If called from another thread, the shutdown is
        ignored (or optionally enforced with a RuntimeError in other backends).

        This ensures that shutdown is always coordinated from a trusted
        context.

        Note:
            Calling `shutdown()` from a non-owning thread has no effect.

        Raises:
            NotOwningError:
                when shutdown is attempted by a non-owning worker.
        """
        with self.locks.owner_lock:
            if self.com is None:
                return

            if not self.com.owning:
                raise NotOwningError

            self.hooks.before_shutdown(self)
            self.com.shutdown()
            self.hooks.after_shutdown(self)
            self.com = None

    def __getstate__(self) -> _ConditionQueueState[T, U, R]:
        """Serializes queue state for persistence or transfer.

        Only minimal state is stored: the hook and shared queue.

        Returns:
            A dictionary containing `hooks` and `com`.
        """
        return _ConditionQueueState(
            hooks=self.hooks,
            com=self.com,
        )

    def __setstate__(self, state: _ConditionQueueState[T, U, R]) -> None:
        """Restores a queue instance from serialized state.

        This uses the stored hook and shared queue to reconstruct
        the original configuration.

        Args:
            state: A dictionary containing `hooks` and `com`,
                   typically returned by `__getstate__()`.
        """
        self.__init__(
            state["hooks"],
            state["com"],
        )


################################################################################
# MOVE ME
################################################################################


@runtime_checkable
class _HasQLock(Protocol):
    def qlock(self) -> LockLike: ...


class ThreadTaskTracker[T]:
    """Tracks unfinished queue tasks and supports blocking joins."""

    __slots__ = ("_cond", "_unfinished", "ack")

    def __init__(self, lock: LockLike) -> None:
        """Initializes a task tracker using the provided lock.

        Args:
            lock: The reentrant lock guarding queue size or state.
        """
        self._cond = import_lazy("threading").Condition(lock)
        self._unfinished = 0
        self.ack = self.task_done

    def new_task(self, item: T | BaseSentinel) -> None:
        if isinstance(item, BaseSentinel):
            return

        with self._cond:
            self._unfinished += 1

    def task_done(self) -> None:
        """Marks a task as completed.

        Decrements the unfinished counter and notifies any waiting joiners
        if all tasks are done.

        Raises:
            TaskDoneOverflowError: If ack() is called too many times.
        """
        with self._cond:
            self._unfinished -= 1
            if self._unfinished < 0:
                raise TaskDoneOverflowError

            if self._unfinished == 0:
                self._cond.notify_all()

    def join(self) -> None:
        """Blocks until all tracked tasks have been marked as done.

        This method is reentrant and safe to call multiple times.
        """
        with self._cond:
            while self._unfinished > 0:
                self._cond.wait()

    @property
    def remaining_tasks(self) -> int:
        """Returns the number of unfinished tasks."""
        return self._unfinished

    @property
    def done(self) -> bool:
        """True if all tasks have been completed."""
        return self._unfinished == 0

    @property
    def condition(self) -> ConditionLike:
        """Returns the internal condition for advanced use (if needed)."""
        return self._cond


class ThreadTaskItem[T](AbstractContextManager[T]):
    """A context manager that tracks task completion on exit."""

    __slots__ = ("item", "tracker")

    def __init__(self, item: T, tracker: ThreadTaskTracker[T]) -> None:
        """Initialize the task context.

        Args:
            item: The queue item being processed.
            tracker: The hook responsible for tracking task completion.
        """
        self.item = item
        self.tracker = tracker

    def __enter__(self) -> T:
        """Enter the task context.

        Returns:
            The wrapped item.
        """
        return self.item

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the task context and mark the task as done."""
        self.tracker.task_done()


class ThreadTaskTrackingHook[Q: _HasQLock, T](
    BaseQueueHook[T, T, ThreadTaskItem[T]]
):
    """Queue hook that tracks unfinished tasks using TaskItem contexts."""

    __slots__ = ("tracker",)

    @override
    def __init__(self, queue: Q) -> None:
        """Initialize the tracking hook and its synchronization state.

        Args:
            queue: The queue this hook is attached to.
        """
        super().__init__()
        self.tracker = ThreadTaskTracker[T](queue.qlock())

    @override
    def after_put(self, queue: object, item: T | BaseSentinel) -> None:
        """Increments unfinished task count after a successful put.

        Args:
            queue: The queue this hook is attached to.
            item: The enqueued item or sentinel.
        """
        self.tracker.new_task(item)

    @override
    def after_get(self, queue: object, item: T) -> ThreadTaskItem[T]:
        """Wraps a dequeued item in a context manager for task tracking.

        Args:
            queue: The queue this hook is attached to.
            item: The dequeued item.

        Returns:
            A TaskItem that manages task completion.
        """
        return ThreadTaskItem(item, self.tracker)

    @override
    def before_shutdown(self, queue: object) -> None:
        """Blocks shutdown until all unfinished tasks are marked done.

        Args:
            queue: The queue this hook is attached to.
        """
        self.tracker.join()
