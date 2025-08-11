# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from asyncio.events import AbstractEventLoop
from collections import deque
from collections.abc import (
    AsyncIterable,
    AsyncIterator,
    Callable,
    Iterable,
    Iterator,
    Sized,
)
from concurrent.futures import Executor
from contextlib import AbstractContextManager
from functools import cached_property
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.sharedctypes import Synchronized
from multiprocessing.synchronize import Condition as ProcessCondition
from threading import Condition as ThreadCondition
from types import ModuleType, TracebackType
from typing import (
    NamedTuple,
    Protocol,
    Self,
    cast,
    override,
    runtime_checkable,
)

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_import import import_lazy


class ShutDown(WhiteprintsError): ...


class Full(WhiteprintsError): ...


class Empty(WhiteprintsError): ...


class TooManyTaskDone(WhiteprintsError): ...


@runtime_checkable
class LockLike(AbstractContextManager[None], Protocol):
    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool: ...

    def release(self) -> None: ...


class TimeoutPair[LockT: LockLike, SemT: LockLike](
    AbstractContextManager[tuple[LockT, SemT | None]]
):
    def __init__(
        self,
        lock: LockT,
        sem: SemT | None = None,
        *,
        blocking: bool = True,
        timeout: float | None = None,
    ):
        self.lock = lock
        self.sem = sem
        self.blocking = blocking
        self.timeout = timeout

    @cached_property
    def _time(self) -> ModuleType:
        return import_lazy("time")

    def _acquire_sem_with_timeout(self, deadline: float | None) -> bool:
        if self.sem is None:
            return True

        if deadline is None:
            self.sem.acquire()
            return True

        remaining = deadline - self._time.monotonic()
        return remaining > 0 and self.sem.acquire(timeout=remaining)

    def _acquire_lock_with_timeout(self, deadline: float | None) -> bool:
        if deadline is None:
            self.lock.acquire(blocking=self.blocking)
            return True

        remaining = deadline - self._time.monotonic()
        return remaining > 0 and self.lock.acquire(
            blocking=self.blocking, timeout=remaining
        )

    def safe_sem_release(self) -> None:
        if self.sem is not None:
            self.sem.release()

    @override
    def __enter__(self) -> tuple[LockT, SemT | None]:
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
        self.lock.release()
        self.safe_sem_release()


@runtime_checkable
class QueueBackend[T](
    AbstractContextManager[None],
    Iterable[T],
    AsyncIterable[T],
    Sized,
    Protocol,
):
    def put(
        self, item: T | None, block: bool, timeout: float | None
    ) -> None: ...

    def get(self, block: bool, timeout: float | None) -> T: ...

    def put_nowait(self, item: T | None) -> None: ...

    def get_nowait(self) -> T: ...

    def task_done(self) -> None: ...

    def shutdown(self) -> None: ...

    def join(self) -> None: ...

    def qsize(self) -> int: ...

    def empty(self) -> bool: ...

    def full(self) -> bool: ...

    def __bool__(self) -> bool: ...

    def __len__(self) -> int: ...

    def __iter__(self) -> Iterator[T]: ...

    def __aiter__(self) -> AsyncIterator[T]: ...

    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def aput(
        self,
        item: T | None,
        executor: Executor | None,
        loop: AbstractEventLoop | None = None,
    ) -> None: ...

    async def aget(
        self, executor: Executor | None, loop: AbstractEventLoop | None = None
    ) -> T: ...


class ThreadBackend[T](QueueBackend[T]):
    def __init__(self, maxsize: int = 0):
        self.maxsize = maxsize
        self._init(maxsize)

        threading = import_lazy("threading")
        self.mutex = threading.Lock()
        self.not_empty = threading.Condition(self.mutex)
        self.not_full = threading.Condition(self.mutex)
        self.all_tasks_done = threading.Condition(self.mutex)

        self.unfinished_tasks: int = 0
        self.is_shutdown: bool = False

        self._size_counter: int = 0

    @staticmethod
    def _time() -> float:
        return import_lazy("time").monotonic()

    def _fail_if_shutdown(self) -> None:
        if self.is_shutdown:
            raise ShutDown

    @staticmethod
    def _wait_forever_until(
        predicate: Callable[[], bool], cond: ThreadCondition
    ) -> None:
        while not predicate():
            cond.wait()

    def _wait_with_timeout_until(
        self,
        predicate: Callable[[], bool],
        cond: ThreadCondition,
        timeout: float,
        err: Exception,
    ) -> None:
        endtime = self._time() + timeout
        while not predicate():
            remaining = endtime - self._time()
            if remaining <= 0:
                raise err
            cond.wait(remaining)

    def _wait_for(
        self,
        predicate: Callable[[], bool],
        cond: ThreadCondition,
        timeout: float | None,
        err: Exception,
    ) -> None:
        if timeout is None:
            self._wait_forever_until(predicate, cond)
        else:
            self._wait_with_timeout_until(predicate, cond, timeout, err)

    def _wait_until_not_full(self, timeout: float | None) -> None:
        self._wait_for(
            predicate=lambda: self.qsize() < self.maxsize,
            cond=self.not_full,
            timeout=timeout,
            err=Full(),
        )

    def _wait_until_not_empty(self, timeout: float | None) -> None:
        self._wait_for(
            predicate=lambda: self.qsize() > 0,
            cond=self.not_empty,
            timeout=timeout,
            err=Empty(),
        )

    @override
    def put(
        self, item: T | None, block: bool = True, timeout: float | None = None
    ) -> None:
        with self.not_full:
            self._fail_if_shutdown()

            if self.maxsize > 0 and self.qsize() >= self.maxsize:
                if not block:
                    raise Full

                self._wait_until_not_full(timeout)
                self._fail_if_shutdown()

            self._put(item)
            self._size_counter += 1
            self.unfinished_tasks += 1
            self.not_empty.notify()

    def _fail_if_shutdown_and_empty(self) -> None:
        if self.is_shutdown and not self.qsize():
            raise ShutDown

    def _wait_for_item(self, timeout: float | None) -> None:
        self._wait_for(
            predicate=lambda: self.qsize() > 0,
            cond=self.not_empty,
            timeout=timeout,
            err=Empty(),
        )

    @override
    def get(self, block: bool = True, timeout: float | None = None) -> T:
        with self.not_empty:
            self._fail_if_shutdown_and_empty()

            if not block and not self.qsize():
                raise Empty

            if block and not self.qsize():
                self._wait_for_item(timeout)
                self._fail_if_shutdown_and_empty()

            item = self._get()
            self._size_counter -= 1
            self.not_full.notify()

            if item is None:
                self.shutdown()
                raise ShutDown

            return item

    @override
    def put_nowait(self, item: T | None) -> None:
        return self.put(item, block=False)

    @override
    def get_nowait(self) -> T:
        return self.get(block=False)

    @override
    def task_done(self) -> None:
        with self.all_tasks_done:
            unfinished = self.unfinished_tasks - 1
            if unfinished < 0:
                raise TooManyTaskDone

            self.unfinished_tasks = unfinished
            if unfinished == 0:
                self.all_tasks_done.notify_all()

    @override
    def shutdown(self) -> None:
        if self.is_shutdown:
            return

        with self.mutex:
            self.is_shutdown = True
            self.not_empty.notify_all()
            self.not_full.notify_all()

    @override
    def join(self) -> None:
        with self.all_tasks_done:
            while self.unfinished_tasks:
                self.all_tasks_done.wait()

    @override
    def qsize(self) -> int:
        with self.mutex:
            return self._size_counter

    @override
    def empty(self) -> bool:
        with self.mutex:
            return self._size_counter == 0

    @override
    def full(self) -> bool:
        with self.mutex:
            return self.maxsize > 0 and self._size_counter >= self.maxsize

    @override
    async def aput(
        self,
        item: T | None,
        executor: Executor | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> None:
        if loop is None:
            await (
                import_lazy("asyncio.events")
                .get_running_loop()
                .run_in_executor(executor, self.put, item)
            )
            return

        await loop.run_in_executor(executor, self.put, item)

    @override
    async def aget(
        self,
        executor: Executor | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> T:
        if loop is None:
            return (
                await import_lazy("asyncio.events")
                .get_running_loop()
                .run_in_executor(executor, self.get)
            )

        return await loop.run_in_executor(executor, self.get)

    @override
    def __bool__(self) -> bool:
        return not self.is_shutdown and not self.empty()

    @override
    def __len__(self) -> int:
        return self.qsize()

    @override
    def __iter__(self) -> Iterator[T]:
        while True:
            try:
                yield self.get()
            except ShutDown as shutdown:
                raise StopIteration from shutdown

    @override
    async def __aiter__(self) -> AsyncIterator[T]:
        while True:
            try:
                yield await self.aget()
            except ShutDown as shutdown:
                raise StopIteration from shutdown

    @override
    def __enter__(self) -> None:
        return

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    def _init(self, _maxsize: int) -> None:
        self.queue: deque[T | None] = deque()

    def _put(self, item: T | None) -> None:
        self.queue.append(item)

    def _get(self) -> T | None:
        return self.queue.popleft()


class _ProcessQueueState(NamedTuple):
    maxsize: int
    reader: Connection | None
    writer: Connection | None
    rlock: LockLike
    wlock: LockLike
    sem: LockLike | None
    unfinished_tasks: Synchronized[int]
    task_cond: ProcessCondition
    size_counter: Synchronized[int]
    ctx_name: str
    is_shutdown: Synchronized[bool]


class ProcessBackend[T](QueueBackend[T]):
    def __init__(
        self,
        maxsize: int = 0,
        ctx: BaseContext | None = None,
    ) -> None:
        self.ctx = ctx or import_lazy("multiprocessing").get_context()
        self.maxsize = maxsize

        self._reader, self._writer = self.ctx.Pipe(duplex=False)
        self._rlock = cast("LockLike", self.ctx.Lock())
        self._wlock = cast("LockLike", self.ctx.Lock())

        self._sem = (
            cast("LockLike", self.ctx.BoundedSemaphore(maxsize))
            if maxsize > 0
            else None
        )

        # Task tracking
        self._unfinished_tasks = self.ctx.Value("i", 0)
        self._task_cond = self.ctx.Condition(self.ctx.Lock())

        # Size tracking for qsize()
        self._size_counter = self.ctx.Value("i", 0)

        selectors = import_lazy("selectors")
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._reader.fileno(), selectors.EVENT_READ)

        self._is_shutdown = self.ctx.Value("b", False)

    def _close_selector(self) -> None:
        if self._selector is not None:
            if self._reader is not None:
                self._selector.unregister(self._reader.fileno())

            self._selector.close()
            self._selector = None

    def lock_reader(self) -> Self:
        if self._writer is not None:
            with self._wlock:
                if self._writer is not None:
                    self._writer.close()
                    self._writer = None

        return self

    def lock_writer(self) -> Self:
        if self._reader is not None:
            with self._rlock:
                if self._reader is not None:
                    self._close_selector()
                    self._reader.close()
                    self._reader = None

        return self

    def _poll(self, timeout: float | None) -> bool:
        if self._selector is None:
            raise ShutDown

        return bool(self._selector.select(timeout))

    @cached_property
    def _struct(self) -> ModuleType:
        return import_lazy("struct")

    def _encode(self, obj: T | None) -> bytes:
        data = import_lazy("multiprocessing.reduction").ForkingPickler.dumps(
            obj
        )
        return self._struct.pack("!I", len(data)) + data

    @staticmethod
    def _decode(raw: bytes) -> T:
        return import_lazy("multiprocessing.reduction").ForkingPickler.loads(
            raw
        )

    def _fail_if_shutdown(self) -> Connection:
        if self.is_shutdown or self._writer is None:
            raise ShutDown

        return self._writer

    def _fail_if_shutdown_and_empty(self) -> Connection:
        if (self.is_shutdown and self.empty()) or self._reader is None:
            raise ShutDown

        return self._reader

    @override
    def put(
        self, item: T | None, block: bool = True, timeout: float | None = None
    ) -> None:
        writer = self._fail_if_shutdown()

        try:
            with TimeoutPair(
                self._wlock, self._sem, blocking=block, timeout=timeout
            ):
                writer.send_bytes(self._encode(item))
        except TimeoutError as timeout_error:
            raise Full from timeout_error

        with self._task_cond:
            self._unfinished_tasks.value += 1
            self._task_cond.notify_all()

        with self._size_counter.get_lock():
            self._size_counter.value += 1

    def _wait_non_empty(self, *, block: bool, timeout: float | None) -> None:
        if block and not self._poll(timeout):
            raise Empty

        if not block and not self._poll(0):
            raise Empty

    @override
    def get(self, block: bool = True, timeout: float | None = None) -> T:
        reader = self._fail_if_shutdown_and_empty()
        self._wait_non_empty(block=block, timeout=timeout)

        with self._rlock:
            try:
                header = reader.recv_bytes(4)
                (size,) = self._struct.unpack("!I", header)
                data = reader.recv_bytes(size)
            except (OSError, EOFError) as recv_error:
                raise ShutDown from recv_error

        if self._sem:
            self._sem.release()

        with self._size_counter.get_lock():
            self._size_counter.value -= 1

        item = self._decode(data)
        if item is None:
            self.shutdown()
            raise ShutDown

        return item

    @override
    def task_done(self) -> None:
        with self._task_cond:
            unfinished = self._unfinished_tasks.value - 1
            if unfinished < 0:
                raise TooManyTaskDone

            self._unfinished_tasks.value = unfinished
            if unfinished == 0:
                self._task_cond.notify_all()

    @override
    def join(self) -> None:
        with self._task_cond:
            while self._unfinished_tasks.value > 0:
                self._task_cond.wait()

    @override
    def qsize(self) -> int:
        with self._size_counter.get_lock():
            return self._size_counter.value

    @override
    def empty(self) -> bool:
        return self.qsize() == 0

    @override
    def full(self) -> bool:
        if self._sem is None:
            return False

        with self._size_counter.get_lock():
            return self._size_counter.value >= self.maxsize

    @override
    def put_nowait(self, item: T | None) -> None:
        return self.put(item, block=False)

    @override
    def get_nowait(self) -> T:
        return self.get(block=False)

    @override
    async def aput(
        self,
        item: T | None,
        executor: Executor | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> None:
        if loop is None:
            await (
                import_lazy("asyncio.events")
                .get_running_loop()
                .run_in_executor(executor, self.put, item)
            )
            return

        await loop.run_in_executor(executor, self.put, item)

    @override
    async def aget(
        self,
        executor: Executor | None = None,
        loop: AbstractEventLoop | None = None,
    ) -> T:
        if loop is None:
            return (
                await import_lazy("asyncio.events")
                .get_running_loop()
                .run_in_executor(executor, self.get)
            )

        return await loop.run_in_executor(executor, self.get)

    @override
    def __bool__(self) -> bool:
        return not self.is_shutdown and not self.empty()

    @override
    def __len__(self) -> int:
        return self.qsize()

    @override
    def __iter__(self) -> Iterator[T]:
        while True:
            try:
                yield self.get()
            except ShutDown as shutdown:
                raise StopIteration from shutdown

    @override
    async def __aiter__(self) -> AsyncIterator[T]:
        while True:
            try:
                yield await self.aget()
            except ShutDown as shutdown:
                raise StopIteration from shutdown

    @override
    def __enter__(self) -> None:
        return

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    @property
    def is_shutdown(self) -> bool:
        return self._is_shutdown.value

    @override
    def shutdown(self) -> None:
        with self._task_cond:
            self._is_shutdown.value = True
            self._task_cond.notify_all()

        self.lock_reader()
        self.lock_writer()

    def _reset_selector(self) -> None:
        selectors = import_lazy("selectors")
        self._selector = selectors.DefaultSelector()

        if self._reader is not None:
            self._selector.register(
                self._reader.fileno(), selectors.EVENT_READ
            )

    def __getstate__(self) -> _ProcessQueueState:
        import_lazy("multiprocessing.context").assert_spawning(self)

        return _ProcessQueueState(
            maxsize=self.maxsize,
            reader=self._reader,
            writer=self._writer,
            rlock=self._rlock,
            wlock=self._wlock,
            sem=self._sem,
            unfinished_tasks=self._unfinished_tasks,
            task_cond=self._task_cond,
            size_counter=self._size_counter,
            ctx_name=self.ctx.get_start_method(),
            is_shutdown=self._is_shutdown,
        )

    def __setstate__(self, state: _ProcessQueueState) -> None:
        mp = import_lazy("multiprocessing")
        ctx = mp.get_context(state.ctx_name)

        self.ctx = ctx
        self.maxsize = state.maxsize
        self._reader = state.reader
        self._writer = state.writer
        self._rlock = state.rlock
        self._wlock = state.wlock
        self._sem = state.sem
        self._unfinished_tasks = state.unfinished_tasks
        self._task_cond = state.task_cond
        self._size_counter = state.size_counter
        self._is_shutdown = state.is_shutdown
