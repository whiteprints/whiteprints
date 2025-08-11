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
from multiprocessing.context import BaseContext
from multiprocessing.synchronize import Lock, RLock
from types import TracebackType
from typing import (
    Any,
    Final,
    Self,
    TypedDict,
    cast,
    override,
)

from whiteprints.lazy_import import import_lazy
from whiteprints.libqueue import BaseSentinel
from whiteprints.libqueue.queue_exceptions import NotOwningError
from whiteprints.libqueue.queue_interface import (
    ConditionLike,
    ConditionQueueLockBackend,
    LockLike,
    QueueCommunicationBackend,
    SynchronizedLike,
)


__all__: Final = [
    "LockUnion",
    "NoCondition",
    "ProcessConditionCommunication",
    "ProcessLockBackend",
]
"""Public module attributes."""


class NoCondition(ConditionLike):
    """No-op multiprocessing-safe condition variable.

    This is a drop-in replacement for a `ConditionLike` where no actual
    blocking or signaling is needed. Used in unbounded queues or minimal
    process-safe coordination where wait/notify are ignored.
    """

    __slots__ = ()

    @override
    def __init__(self) -> None:
        """Initializes the no-op condition."""

    @override
    def __enter__(self) -> None:
        """No-op context manager entry."""

    @override
    def __exit__(
        self,
        /,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """No-op context manager exit."""

    @override
    def wait(self, timeout: float | None = None) -> bool:
        """Immediately returns True without blocking.

        Args:
            timeout: Ignored.

        Returns:
            Always True.
        """
        return True

    @override
    def wait_for(
        self,
        predicate: Callable[[], bool],
        timeout: float | None = None,
    ) -> bool:
        """Immediately evaluates and returns predicate result.

        Args:
            predicate: A callable returning a bool.
            timeout: Ignored.

        Returns:
            The result of the predicate.
        """
        return predicate()

    @override
    def notify(self, n: int = 1) -> None:
        """No-op notify method.

        Args:
            n: Ignored.
        """

    @override
    def notify_all(self) -> None:
        """No-op notify_all method."""

    def __getstate__(self) -> Callable[[], bool]:
        """Serialization hook used during multiprocessing spawn.

        Returns:
            The `acquire` method, passed to the new process.
        """
        import_lazy("multiprocessing.context").assert_spawning(self)
        return self.acquire

    def __setstate__(self, state: Callable[[], bool]) -> None:
        """Deserialization hook used during multiprocessing spawn.

        Args:
            state: The callable to set as the acquire method.
        """
        self.acquire = state


class LockUnion(LockLike):
    """A protocol for lock-like objects supporting context management.

    This abstraction describes any object with `acquire()` and `release()`
    methods, as well as support for use in `with` blocks.

    Implementations include `threading.Lock`, `threading.Semaphore`,
    `multiprocessing.Lock`, etc.
    """

    @override
    def __init__(self, lock1: LockLike, lock2: LockLike) -> None:
        self.lock1 = lock1
        self.lock2 = lock2

    def acquire(self, /, *args: Any, **kwargs: Any) -> bool:
        """Acquires the lock.

        Args:
            args: acquire args to forward.
            kwargs: acquire kwargs to forward.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        lock1 = self.lock1.acquire(*args, **kwargs)
        lock2 = self.lock2.acquire(*args, **kwargs)
        return lock1 and lock2

    @override
    def release(self) -> None:
        """Releases the lock."""
        self.lock2.release()
        self.lock1.release()

    def __enter__(self) -> object:
        """Enter the lock's context and acquire the lock."""
        self.lock1.acquire()
        self.lock2.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exit the lock's context and release the lock."""
        self.lock2.release()
        self.lock1.release()


class _ProcessLockBackendState(TypedDict):
    maxsize: int
    owner_lock: LockLike
    queue_lock: LockLike
    pipe_read_lock: LockLike
    pipe_write_lock: LockLike


class ProcessLockBackend(ConditionQueueLockBackend):
    __slots__ = (
        "bounded",
        "ctx",
        "maxsize",
        "not_empty",
        "not_full",
        "notify_not_empty",
        "notify_not_full",
        "owner_lock",
        "pipe_read_lock",
        "pipe_write_lock",
        "queue_lock",
    )

    def __init__(
        self, maxsize: int, *, ctx: BaseContext | None = None
    ) -> None:
        self.ctx = ctx or import_lazy("multiprocessing").get_context()
        self.maxsize = maxsize
        self.owner_lock = self.create_rlock()
        self.pipe_read_lock = self.create_rlock()
        self.pipe_write_lock = self.create_rlock()
        self.init_conditions()

    @override
    def create_rlock(self) -> RLock:
        return self.ctx.RLock()

    @override
    def create_lock(self) -> Lock:
        return self.ctx.Lock()

    def init_conditions(self) -> Self:
        self.bounded = self.maxsize > 0
        self.queue_lock = LockUnion(
            self.pipe_write_lock,
            self.pipe_read_lock,
        )
        self.bind_methods()
        return self

    def bind_methods(self) -> None:
        self.not_full = NoCondition()
        self.not_empty = NoCondition()
        self.notify_not_full = lambda: None
        self.notify_not_empty = lambda: None

    def __getstate__(self) -> _ProcessLockBackendState:
        import_lazy("multiprocessing.context").assert_spawning(self)
        return _ProcessLockBackendState(
            maxsize=self.maxsize,
            owner_lock=self.owner_lock,
            queue_lock=self.queue_lock,
            pipe_read_lock=self.pipe_read_lock,
            pipe_write_lock=self.pipe_write_lock,
        )

    def __setstate__(self, state: _ProcessLockBackendState) -> None:
        self.ctx = import_lazy("multiprocessing").get_context()
        self.owner_lock = state["owner_lock"]
        self.maxsize = state["maxsize"]
        self.bounded = self.maxsize > 0
        self.queue_lock = state["queue_lock"]
        self.pipe_read_lock = state["pipe_read_lock"]
        self.pipe_write_lock = state["pipe_write_lock"]
        self.bind_methods()


class _ProcessConditionCommunicationState(TypedDict):
    maxsize: int
    reader: Any
    writer: Any
    owner_pid: SynchronizedLike[int]
    is_shutdown: SynchronizedLike[bool]
    locks: ProcessLockBackend


class ProcessConditionCommunication[U](QueueCommunicationBackend[U]):
    """Default implementation of the process condition communication.

    Provides an in-memory FIFO queue backed by a standard Python deque.
    This implementation is not thread-safe on its own and is intended to
    be used inside a thread-synchronized backend such as `ThreadBackend`.
    """

    __slots__ = (
        "_is_shutdown",
        "_locks",
        "_pipe_read_lock",
        "_pipe_write_lock",
        "_recv_bytes",
        "_send_bytes",
        "ctx",
        "decode",
        "encode",
        "maxsize",
        "owner_pid",
        "owner_tid",
        "reader",
        "true_size",
    )

    @override
    def __init__(
        self,
        maxsize: int,
        *,
        ctx: BaseContext | None = None,
    ) -> None:
        """Initializes the deque-backed shared queue."""
        self.ctx = ctx or import_lazy("multiprocessing").get_context()
        self.maxsize = maxsize
        self.reader, self.writer = self.ctx.Pipe(duplex=False)

        self._locks = ProcessLockBackend(maxsize=self.maxsize, ctx=self.ctx)
        self.owner_pid: SynchronizedLike[int] = self.ctx.Value(
            import_lazy("ctypes").c_int,
            import_lazy("os").getpid(),
            lock=cast("RLock", self.locks.owner_lock),
        )
        self._is_shutdown: SynchronizedLike[bool] = self.ctx.Value(
            import_lazy("ctypes").c_bool,
            False,
            lock=cast("RLock", self.locks.owner_lock),
        )
        self.owner_tid = import_lazy("threading").get_native_id()
        self.bind_methods()
        self.setup_id()

    @property
    def locks(self) -> ProcessLockBackend:
        return self._locks

    def setup_id(self) -> None:
        self.owner_pid: SynchronizedLike[int] = self.ctx.Value(
            import_lazy("ctypes").c_int,
            import_lazy("os").getpid(),
            lock=cast("RLock", self.locks.owner_lock),
        )
        self.owner_tid = import_lazy("threading").get_native_id()

    def readonly(self) -> None:
        with self._is_shutdown:
            self.writer.close()

    def writeonly(self) -> None:
        with self._is_shutdown:
            self.reader.close()

    def close(self) -> None:
        with self._is_shutdown:
            self.reader.close()
            self.writer.close()

    def bind_methods(self) -> None:
        self._send_bytes = self.writer.send_bytes
        self._recv_bytes = self.reader.recv_bytes
        pickler = import_lazy("multiprocessing.reduction").ForkingPickler
        self.encode = pickler.dumps
        self.decode = pickler.loads
        self._pipe_read_lock = self.locks.pipe_read_lock
        self._pipe_write_lock = self.locks.pipe_write_lock

    @override
    def size(self) -> int:
        return int(self.reader.poll())

    @override
    def put(self, item: U | BaseSentinel) -> None:
        data = self.encode(item)
        with self._pipe_write_lock:
            self._send_bytes(data)

    @override
    def get(self) -> U | BaseSentinel:
        with self._pipe_read_lock:
            data = self._recv_bytes()

        return self.decode(data)

    @property
    @override
    def owning(self) -> bool:
        """Returns True if the current process is the queue owner.

        Ownership is defined as the process that originally created the
        queue. Forked or spawned workers will have `owning = False`.

        This check is used to control whether shutdown and finalization
        operations are permitted.

        Returns:
            True if this process owns the queue, False otherwise.
        """
        current_pid = import_lazy("os").getpid()
        current_tid = import_lazy("threading").get_native_id()
        with self.owner_pid:
            return (
                current_pid == self.owner_pid.value
                and current_tid == self.owner_tid
            )

    @override
    def transfer_ownership(self) -> None:
        """Transfers ownership to the current process/thread."""
        current_pid = import_lazy("os").getpid()
        current_tid = import_lazy("threading").get_native_id()
        with self.owner_pid:
            self.owner_pid.value = current_pid
            self.owner_tid = current_tid

    @override
    def revoke_ownership(self) -> None:
        """Removes ownership.

        prevents any process/thread from calling shutdown.
        """
        with self.owner_pid:
            self.owner_pid.value = -1
            self.owner_tid = -1

    @override
    def shutdown(self) -> None:
        with self._is_shutdown:
            if self._is_shutdown.value:
                return

            if not self.owning:
                raise NotOwningError

            self.close()
            self._is_shutdown.value = True

    def __getstate__(self) -> _ProcessConditionCommunicationState:
        import_lazy("multiprocessing.context").assert_spawning(self)
        return _ProcessConditionCommunicationState(
            maxsize=self.maxsize,
            reader=self.reader,
            writer=self.writer,
            owner_pid=self.owner_pid,
            is_shutdown=self._is_shutdown,
            locks=self.locks,
        )

    def __setstate__(self, state: _ProcessConditionCommunicationState) -> None:
        self.ctx = import_lazy("multiprocessing").get_context()
        self.maxsize = state["maxsize"]
        self.reader = state["reader"]
        self.writer = state["writer"]
        self.owner_pid = state["owner_pid"]
        self.owner_tid = -1
        self._locks = state["locks"]
        self._is_shutdown = state["is_shutdown"]
        self.bind_methods()
