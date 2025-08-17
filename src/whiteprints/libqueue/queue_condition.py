# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Condition based implementation of the Whiteprints queue backend.

In-memory queue implementation compatible with the QueueBackend protocol.
It uses condition variables for blocking behavior and supports graceful
shutdown with sentinel-based signaling.

The implementation ensure shutdown and predictable task completion.
"""

from collections.abc import Callable, Container
from textwrap import dedent, indent
from types import FunctionType
from typing import (
    Any,
    ClassVar,
    Final,
    NoReturn,
    TypedDict,
    cast,
    override,
)

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
)
from whiteprints.libqueue.queue_hook import (
    QueueHook,
)
from whiteprints.libqueue.queue_interface import (
    QueueCommunicationBackend,
)


__all__: Final = ["ConditionQueue"]
"""Public module attributes."""

_PUT_SRC_TEMPLATE = dedent("""
    def put[T](self, item: T) -> None:{prepare_put}
        {not_full_acquire}
        try:{inlock_pre_put}
            self._put(item)
        except BaseException as base_error:
            error = self.com.process_error(base_error)
            if not self._not_full_exit_except(
                type(error), error, error.__traceback__
            ):
                raise error from None
        {not_full_release}
""")

_GET_SRC_TEMPLATE = dedent("""
    def get[R](self) -> R:{prepare_get}
        {not_empty_acquire}
        try:{inlock_pre_get}
            {sentinel_get}
        except BaseException as base_error:
            error = self.com.process_error(base_error)
            if not self._not_empty_exit_except(
                type(error), error, error.__traceback__
            ):
                raise error from None
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

    max_slots: int | None
    hooks: QueueHook[T, U, R] | None
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

    hooks: QueueHook[T, U, R]

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
        "get_block",
        "get_timeout",
        "hooks",
        "put",
        "put_block",
        "put_timeout",
        "sentinels",
    )

    @override
    def __init__(
        self,
        max_slots: int | None = None,
        hooks: QueueHook[T, U, R] | None = None,
        com: QueueCommunicationBackend[U] | None = None,
        sentinels: (
            BaseSentinel | type[BaseSentinel] | Container[BaseSentinel] | None
        ) = SHUTDOWN,
        *,
        put_block: bool = True,
        put_timeout: float | None = None,
        get_block: bool = True,
        get_timeout: float | None = None,
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
        super().__init__(
            max_slots,
            hooks,
            com,
            put_block=put_block,
            put_timeout=put_timeout,
            get_block=get_block,
            get_timeout=get_timeout,
        )
        self.put_timeout = put_timeout
        self.get_timeout = get_timeout
        self.put_block = put_block
        self.get_block = get_block
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
            (self.put_timeout is None or self.put_timeout < 0)
            and self.put_block
            and no_prepare_put
            and no_inlock_pre_put
            and no_inlock_post_put
            and no_finalize_put
            and no_acquire
            and no_release
        ):
            self.put = cast("Callable[[T | BaseSentinel], None]", self._put)
            return

        if no_acquire:
            not_full_acquire = ""
        elif not self.put_block or self.put_timeout == 0:
            not_full_acquire = dedent(
                """
                if not self._not_full_acquire(False):
                    raise FullError
                """
            )
        elif self.put_timeout is None or self.put_timeout < 0:
            not_full_acquire = dedent(
                """
                self._not_full_acquire()
                """
            )
        else:
            not_full_acquire = dedent(
                """
                if not self._not_full_acquire(True, self.put_timeout):
                    raise FullError
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
                        if no_inlock_post_put
                        else "\n"
                        "    item = self.hooks.inlock_post_put(self, item)"
                    ),
                    finalize_put=(
                        ""
                        if no_finalize_put
                        else "\nself.hooks.finalize_put(self, item)"
                    ),
                )
            )

        put_src = _PUT_SRC_TEMPLATE.format(
            prepare_put=(
                ""
                if no_prepare_put
                else "\n        item = self.hooks.prepare_put(self, item)"
            ),
            not_full_acquire=indent(not_full_acquire, " " * 4),
            inlock_pre_put=(
                ""
                if no_inlock_pre_put
                else "\n"
                "           item = self.hooks.inlock_pre_put(self, item)"
            ),
            not_full_release=indent(not_full_release, " " * 4),
        )

        local_ns: dict[str, FunctionType] = {}
        exec(put_src, globals(), local_ns)
        self.put = local_ns["put"].__get__(self, self.__class__)

    def _generate_sentinel_code(self) -> str:
        if self.sentinels is None:
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

        return sentinel_get

    def _bind_get(self) -> None:
        no_prepare_get = is_noop(self.hooks.prepare_get)
        no_inlock_pre_get = is_noop(self.hooks.inlock_pre_get)
        no_inlock_post_get = is_noop(self.hooks.inlock_post_get)
        no_finalize_get = is_noop(self.hooks.finalize_get)
        no_acquire = is_noop(self._not_empty_acquire)
        no_release = is_noop(self._not_empty_exit_noexcept)

        if (
            (self.get_timeout is None or self.get_timeout < 0)
            and self.get_block
            and self.sentinels is None
            and no_prepare_get
            and no_inlock_pre_get
            and no_inlock_post_get
            and no_finalize_get
            and no_acquire
            and no_release
        ):
            self.get = cast("Callable[[], R]", self._get)
            return

        sentinel_get = self._generate_sentinel_code()
        if no_acquire:
            not_empty_acquire = ""
        elif not self.get_block or self.get_timeout == 0:
            not_empty_acquire = dedent(
                """
                if not self._not_empty_acquire(False):
                    raise self.EMPTY_ERROR
                """
            )
        elif self.get_timeout is None or self.get_timeout < -1:
            not_empty_acquire = dedent(
                """
                self._not_empty_acquire()
                """
            )
        else:
            not_empty_acquire = dedent(
                """
                if not self._not_empty_acquire(True, self.get_timeout):
                    raise self.EMPTY_ERROR
                """
            )

        if no_release:
            not_empty_release = ""
        else:
            not_empty_release = dedent(
                """
                else:{inlock_post_get}
                    self._not_empty_exit_noexcept(){finalize_get}
                """.format(
                    inlock_post_get=(
                        ""
                        if no_inlock_post_get
                        else "\n    item = self.hooks.inlock_post_get(self)"
                    ),
                    finalize_get=(
                        ""
                        if no_finalize_get
                        else "\nitem = self.hooks.finalize_get(self, item)"
                    ),
                )
            )

        get_src = _GET_SRC_TEMPLATE.format(
            prepare_get=(
                ""
                if no_prepare_get
                else "\n            self.hooks.prepare_get(self)"
            ),
            not_empty_acquire=indent(not_empty_acquire, " " * 4),
            inlock_pre_get=(
                ""
                if no_inlock_pre_get
                else "\n           item = self.hooks.inlock_pre_get(self)"
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
        self._not_empty_exit_except = self._not_empty.exit_except

    @property
    @override
    def is_shutdown(self) -> bool:
        """Indicates whether the queue has been shut down.

        Returns:
            True if shutdown() has been called, False otherwise.
        """
        return self.com is None

    def _shutdown(self, /, *args: Any, **kwargs: Any) -> NoReturn:
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
        if not self.owning:
            raise NotOwningError

        if self.com is None:
            return

        open_put = self.put
        self.hooks.before_shutdown(self)

        # Wake any waiters cleanly (hold each cond just for notify).
        with self.com.producer_null:
            self.com.producer_null.notify_all()

        with self.com.receiver_null:
            self.com.receiver_null.notify_all()

        with self.com.has_receivers:
            self.com.has_receivers.notify_all()

        # Flip callables atomically under owner_lock if you want,
        # but don't call wait_* while holding it.
        with self.locks.owner_lock:
            self.producer = self._shutdown
            self.put = self._shutdown
            self.receiver = self._shutdown

        self.com.wait_no_producers()

        for _tid in list(self.com.receivers):
            open_put(SHUTDOWN)

        self.com.wait_no_receivers()

        with self.locks.owner_lock:
            self.get = self._shutdown
            self.com.shutdown()
            self.com = None

        self.hooks.after_shutdown(self)

    def __getstate__(self) -> _ConditionQueueState[T, U, R]:
        """Serializes queue state for persistence or transfer.

        Only minimal state is stored: the hook and shared queue.

        Returns:
            A dictionary containing `hooks` and `com`.
        """
        return _ConditionQueueState(
            max_slots=self.max_slots,
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
            state["max_slots"],
            state["hooks"],
            state["com"],
        )
