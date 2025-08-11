# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Lock-like interface for queue-safe synchronization primitives.

Defines a generic protocol for context-manageable lock objects used to
guard queue operations in concurrent environments.
"""

from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager
from types import TracebackType
from typing import (
    Any,
    Final,
    Protocol,
    Self,
    runtime_checkable,
)

from whiteprints.libqueue import BaseSentinel


__all__: Final = [
    "LockLike",
    "QueueCommunicationBackend",
    "QueueHook",
    "QueueInterface",
    "SynchronizedLike",
]
"""Public module attributes."""


@runtime_checkable
class LockLike(Protocol):
    """A protocol for lock-like objects supporting context management.

    This abstraction describes any object with `acquire()` and `release()`
    methods, as well as support for use in `with` blocks.

    Implementations include `threading.Lock`, `threading.Semaphore`,
    `multiprocessing.Lock`, etc.
    """

    def acquire(self, /, *args: Any, **kwargs: Any) -> bool:
        """Acquires the lock.

        Args:
            args: acquire args to forward.
            kwargs: acquire kwargs to forward.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        ...

    def release(self) -> None:
        """Releases the lock."""
        ...

    def __enter__(self) -> object:
        """Enter the lock's context and acquire the lock."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exit the lock's context and release the lock."""
        ...


@runtime_checkable
class SynchronizedLike[T](Protocol):
    """Runtime-checkable protocol for multiprocessing.Value-like objects.

    This captures shared memory wrappers like Synchronized[int], which expose
    a `.value` field for getting and setting the shared state.
    """

    value: T

    def get_lock(self) -> LockLike:
        """Returns the internal lock object used for synchronization."""
        ...

    def __enter__(self) -> T:
        """Enter the synchronized's context and acquire the internal lock."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exit the synchronized's context and release the internal lock."""
        ...


@runtime_checkable
class ConditionLike(Protocol):
    """Synchronization primitive supporting wait/notify and locking.

    This protocol represents condition variables used for coordinating
    threads or processes. Compatible with `threading.Condition` and
    `multiprocessing.Condition`.
    """

    def __init__(self, lock: LockLike | None = None) -> None:
        """Initialize the condition with an optional external lock.

        Args:
            lock: A reentrant lock object to associate with the condition.
                  If None, a new internal lock will be created.
        """
        ...

    def acquire(self, /, *args: Any, **kwargs: Any) -> bool:
        """Acquires the lock.

        Args:
            args: acquire args to forward.
            kwargs: acquire kwargs to forward.

        Returns:
            True if the lock was acquired, False otherwise.
        """
        ...

    def release(self) -> None:
        """Releases the lock."""
        ...

    def __enter__(self) -> None:
        """Enter the condition's context and acquire the internal lock."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exit the condition's context and release the internal lock."""
        ...

    def wait(self, timeout: float | None = None) -> bool:
        """Block until notified or until the optional timeout expires.

        Args:
            timeout: Optional timeout in seconds. If None, waits indefinitely.
        """
        ...

    def wait_for(
        self,
        predicate: Callable[[], bool],
        timeout: float | None,
    ) -> bool:
        """Block until predicate is true or until the optional timeout.

        Repeatedly evaluates the predicate and waits if it returns False.

        Args:
            predicate: A callable that returns True to break the wait loop.
            timeout: Optional timeout in seconds.

        Returns:
            True if the predicate returned True, False if timeout expired.
        """
        ...

    def notify(self, n: int = 1) -> None:
        """Wake up `n` threads or processes waiting on this condition.

        Args:
            n: The number of waiting entities to notify (default is 1).
        """
        ...

    def notify_all(self) -> None:
        """Wake all threads or processes waiting on this condition."""
        ...


@runtime_checkable
class SemaphoreLike(AbstractContextManager[object], Protocol):
    """A protocol for semaphore-like synchronization primitives.

    Compatible with threading.Semaphore, multiprocessing.Semaphore,
    and custom semaphore implementations that support blocking control
    via `acquire()`/`release()` and context management.

    Example:
        with semaphore:
            # critical section
    """

    def __init__(self, value: int = 1) -> None:
        """Initialize the semaphore with a given initial value.

        Args:
            value: Initial semaphore count (defaults to 1).
        """
        ...

    def acquire(self, /, *args: Any, **kwargs: Any) -> bool:
        """Acquires the semaphore, blocking if necessary.

        Returns:
            True if the semaphore was acquired.
        """
        ...

    def release(self) -> None:
        """Releases the semaphore, incrementing its internal counter."""
        ...

    def __enter__(self) -> object:
        """Enter context: acquire the semaphore."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        """Exit context: release the semaphore."""
        ...


@runtime_checkable
class CrossContext(SemaphoreLike, Protocol):

    def exit_except(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        /,
    ) -> None:
        ...

    def exit_noexcept(self) -> None:
        ...


@runtime_checkable
class QueueLockBackend(Protocol):
    queue_lock: LockLike
    owner_lock: LockLike
    not_full: CrossContext
    not_empty: CrossContext

    def __init__(self) -> None:
        """Initializes the lock backend with internal synchronization."""
        ...

    def create_lock(self) -> LockLike:
        """Creates a standard (non-reentrant) lock instance.

        Returns:
            A new instance of a basic lock object.
        """
        ...

    def create_rlock(self) -> LockLike:
        """Creates a reentrant lock instance.

        Returns:
            A new instance of a reentrant lock object.
        """
        ...


@runtime_checkable
class QueueCommunicationBackend[U](Protocol):
    """Protocol for basic shared FIFO queues.

    This interface defines the core operations required by a shared queue
    implementation, including insertion, removal, and state introspection.
    It is designed to work alongside a synchronization backend like to provide
    safe FIFO behavior.

    The type parameter `U` represents the type returned by `get()`.

    Slot/Item Abstraction:
        This protocol uses a conceptual separation between *slots* and *items*:

        - A **slot** represents capacity available for a producer to insert
          an item. Bounded queues use a semaphore to enforce this limit.
        - An **item** is a unit of data placed into the queue and consumed
          by a receiver.

        Unlike traditional `.qsize()`, this abstraction avoids reliance on
        potentially inaccurate or lock-requiring size queries. It supports
        efficient coordination in lock-minimized or lock-free designs.

    Attributes:
        max_slots:
            The maximum number of concurrent producer slots.
            - If set to an integer > 0, the queue is bounded.
            - If None, the queue is unbounded and has infinite slots.
        locks:
            The synchronization primitives (e.g., conditions or semaphores)
            associated with this queue backend. Used to coordinate access
            across threads.
    """
    max_slots: int | None
    locks: QueueLockBackend

    def __init__(self, max_slots: int | None) -> None:
        """Initializes the queue communication backend.

        Args:
            max_slots: The maximum number of producer slots allowed.
                - If set to an integer > 0, the queue is bounded.
                - If None, the queue is unbounded.
        """
        ...

    def put(self, item: U | BaseSentinel) -> None:
        """Inserts an item or sentinel into the queue.

        Args:
            item: The item or sentinel to enqueue.
        """
        ...

    def get(self) -> U | BaseSentinel:
        """Retrieves and removes the next item from the queue.

        Returns:
            The dequeued item or sentinel.
        """
        ...

    @property
    def owning(self) -> bool:
        """Whether the current thread is allowed to perform shutdown.

        The queue backend tracks per-thread ownership using a thread-local
        flag. By default, the thread that created the queue is marked as the
        owner (`owning=True`), while other threads will see `owning=False`.

        Ownership determines whether the current thread is permitted to call
        `shutdown()` or trigger shutdown during finalization (`__del__`).

        Returns:
            True if the current thread is considered the queue owner, False
            otherwise.

        Note:
            If a non-owning thread mistakenly retains `owning=True` (e.g., via
            object sharing without proper transfer of lifecycle control), it
            may
            garbage-collected.
        """
        ...

    def transfer_ownership(self) -> None:
        """Transfers ownership to the current worker."""
        ...

    def revoke_ownership(self) -> None:
        """Revokes ownership from the current thread.

        Prevents the current thread from performing operations restricted to
        the owner, such as shutdown.
        """
        ...

    def shutdown(self) -> None:
        """Shuts down the queue communication layer.

        This method releases any held resources and unblocks waiting
        operations. It should be called when the queue is no longer needed.
        """
        ...


@runtime_checkable
class QueueHook[Q, T, U, R](Protocol):
    """Lifecycle and instrumentation hooks for queue operations.

    This protocol enables injection of custom logic at key points in the
    lifecycle of a queue instance — including initialization, shutdown,
    enqueue (`put`), dequeue (`get`), and sentinel handling.

    Hook methods are structured to distinguish between:

      - Stateless transformations (e.g., `prepare_put`, `finalize_put`,
        `finalize_get`), which operate outside of any lock and should avoid
        mutating the queue.
      - In-lock instrumentation (`inlock_pre_put`, `inlock_post_put`,
        `inlock_pre_get`, `inlock_post_get`), which operate under the queue's
        synchronization lock and are intended for coordination logic that
        requires mutual exclusion.
      - Lifecycle methods (`after_init`, `after_shutdown`, `before_shutdown`),
        which provide points for setup and teardown behavior around the queue's
        usage.

    Type parameters:
        Q: The queue type this hook is bound to.
        T: The type accepted by the public `put()` method.
        U: The internal representation stored in the queue (output of
           `prepare_put()`).
        R: The type returned by the public `get()` method (output of
           `finalize_get()`).

    Usage guidance for in-lock hooks:
        The `inlock_*` methods are intended for lightweight, lock-safe
        operations. It is strongly recommended that these methods avoid:

            1. Acquiring other locks held by the queue (especially non-
               reentrant locks).
            2. Performing heavy computations or I/O.
            3. Mutating the queue itself or its internal coordination
               structures.

        Violating these constraints may lead to deadlocks or degraded
        throughput under concurrency.

        These recommendations are not enforced — experienced developers who
        fully understand the queue's locking model may safely apply more
        advanced patterns when needed. However, careful design is required to
        avoid introducing contention or subtle bugs.

        When in doubt, use `prepare_*` and `finalize_*` for non-critical
        transformations, and reserve `inlock_*` for synchronization-aware
        instrumentation only.
    """

    def after_init(self, queue: Q) -> None:
        """Called after the queue and hook are fully initialized.

        Args:
            queue: the hooked queue.
        """
        ...

    def before_shutdown(self, queue: Q) -> None:
        """Called before queue shutdown begins.

        Args:
            queue: the hooked queue.
        """
        ...

    def after_shutdown(self, queue: Q) -> None:
        """Called after queue shutdown completes.

        Args:
            queue: the hooked queue.
        """
        ...

    def prepare_put(
        self, queue: Q, item: T | BaseSentinel,
    ) -> U | BaseSentinel:
        """Called before an item is enqueued.

        Use this to convert the external input into an internal queue
        representation. Should be pure and stateless.

        Example uses:
            - Serialization
            - Wrapping with metadata
            - Priority tagging

        Note:
            This operates outside of any lock.

        Args:
            queue: the hooked queue.
            item: The original item or sentinel to enqueue.

        Returns:
            The item to pass to the queue (may be transformed).
        """
        ...

    def inlock_pre_put(
        self, queue: Q, item: U | BaseSentinel
    ) -> None:
        """Called before an item is enqueued and after it's prepared.

        Use this to update queue-owned state based on the item or
        coordinate inter-thread/process logic.

        Example uses:
            - Reference counting
            - In-place state updates
            - Instrumentation

        Note:
            This operates in a lock.

        Args:
            queue: the hooked queue.
            item: The original item or sentinel to enqueue.

        Returns:
            The item to pass to the queue (may be transformed).
        """
        ...

    def inlock_post_put(
        self, queue: Q, item: U | BaseSentinel
    ) -> None:
        """Postprocess an item after it is successfully enqueued.

        Used to perform post-enqueue adjustments that must be atomic
        with queue state.

        Example uses:
            - Coherent metrics update
            - Condition signaling refinement

        Note:
            This operates in a lock.

        Args:
            queue: the hooked queue.
            item: The item or sentinel that was added.

        Returns:
            The item added to the queue (may be transformed).
        """
        ...

    def finalize_put(self, queue: Q, item: U | BaseSentinel) -> None:
        """Called after an item is successfully enqueued.

        Use this for logging, metrics, or external signaling.

        Note:
            This operates outside of any lock.

        Args:
            queue: the hooked queue.
            item: The item or sentinel that was added.
        """
        ...

    def prepare_get(self, queue: Q) -> None:
        """Called before an item is retrieved.

        Use this to prepare external state or apply sampling logic.

        Note:
            This operates outside of any lock.

        Args:
            queue: the hooked queue.
        """
        ...

    def inlock_pre_get(self, queue: Q) -> None:
        """Called before an item is retrieved.

        Used to coordinate access or inspect internal state.

        Note:
            This operates in a lock.

        Args:
            queue: the hooked queue.
        """
        ...

    def inlock_post_get(self, queue: Q) -> None:
        """Called after an item is retrieved.

        Use this for bookkeeping that must be consistent with queue state.

        Note:
            This operates in a lock.

        Args:
            queue: the hooked queue.
        """
        ...

    def finalize_get(self, queue: Q, item: U) -> R:
        """Transforms the retrieved item into its final output.

        Example uses:
            - Deserialization
            - Reference release
            - Result unwrapping

        Note:
            This operates outside of any lock.

        Args:
            queue: the hooked queue.
            item: The dequeued item.

        Returns:
            The item to return to the consumer (may be transformed).
        """
        ...

    def on_get_sentinel(
        self,
        queue: Q,
        sentinel: BaseSentinel,
        exception: Exception | None = None,
    ) -> Exception:
        """Converts a sentinel into an exception to raise.

        Called when a sentinel is dequeued and not handled internally.

        Args:
            queue: The hooked queue instance.
            sentinel: The retrieved sentinel object.
            exception: Optional inner exception (e.g., from prior hooks).

        Returns:
            The exception to raise from `get()`.
        """
        ...


@runtime_checkable
class QueueSyncOps[T, U, R](
    Iterable[R],
    Protocol,
):
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

    hooks: QueueHook["QueueInterface[T, U, R]", T, U, R]
    com: QueueCommunicationBackend[U] | None

    put: Callable[[T | BaseSentinel], None]
    get: Callable[[], R]

    def __init__(
        self,
        hooks: QueueHook[object, T, U, R] | None,
        com: QueueCommunicationBackend[U] | None,
    ) -> None:
        """Initializes the queue and attaches the given hook type.

        The hook is a class implementing `QueueHook`, instantiated
        with a reference to this queue. The resulting instance is used
        to observe or mutate lifecycle events such as put(), get(),
        shutdown(), and task tracking.

        Args:
            hooks: A `QueueHookBase` class or factory function.
                You may pass a hook class (e.g., `LoggingHook`) or a factory
                like `lambda q: LoggingHook(q, arg)` to inject parameters.
            com: Implementation of the SharedQueue protocol.
        """
        ...

    @property
    def locks(self) -> QueueLockBackend:
        ...

    @property
    def full(self) -> bool:
        """Checks if the queue has reached its maximum capacity.

        Returns:
            True if the queue is full, False otherwise.

        Warning:
            This method is not inherently thread- or process-safe unless used
            inside a `qlock()` context. The size may change immediately
            after the method returns, especially under high concurrency.

        Preferred pattern:

            with queue.qlock():
                if queue.full():
                    ...
        """
        ...

    @property
    def empty(self) -> bool:
        """Checks if the queue is currently empty.

        Returns:
            True if there are no items in the queue, False otherwise.

        Warning:
            This method is not inherently thread- or process-safe unless the
            result is used inside a `qlock()` context. The size may change
            immediately after this method returns due to concurrent producers
            or consumers.

        Preferred pattern:

            with queue.qlock():
                if queue.empty():
                    ...
        """
        ...

    def __iter__(self) -> Iterator[R]:
        """Iterates over items in the queue until shutdown.

        Yields:
            Items from the queue.

        Stops:
            When a ShutDownError is raised.
        """
        ...

    def dispatch[K](
        self,
        *,
        dispatcher: Callable[[R], K],
        queue_sinks: Mapping[K, object],
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
        ...


@runtime_checkable
class QueueLifecycle[T, U, R](
    QueueSyncOps[T, U, R], AbstractContextManager[None], Protocol
):
    """Queue interface for shutdown, task tracking, and cleanup.

    This protocol defines lifecycle-related methods that govern the state
    of the queue. It includes shutdown control, task tracking, and context
    manager support for automatic resource cleanup.

    This interface builds on QueueSyncOps and assumes the presence of a
    shutdown-aware backend.
    """

    finalizer: Callable[[], None]

    @property
    def owning(self) -> bool:
        """Whether the current thread is allowed to perform shutdown."""
        ...

    @property
    def is_shutdown(self) -> bool:
        """Indicates whether the queue has been shut down."""
        ...

    def shutdown(self) -> None:
        """Shuts down the queue and unblocks any waiting consumers.

        Only the context (thread or process) that owns the queue is permitted
        to call this method. Ownership is defined by the backend and enforced
        via the `owning` property.
        """
        ...

    def send_shutdown(self) -> None:
        """Signals shutdown by inserting a sentinel into the queue.

        This is a convenience wrapper that allows consumers to exit
        cleanly by detecting the sentinel.
        """
        ...

    def close(self) -> Self:
        """Shuts down the queue and returns self.

        This is useful in fluent interfaces or when chaining methods.

        Returns:
            self
        """
        ...

    def __enter__(self) -> None:
        """No-op context manager entry point."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Shuts down the queue on context manager exit, if owned.

        current thread is not the queue owner, the shutdown may be skipped or
        raise an error.

        Args:
            exc_type: The exception type, if raised.
            exc_val: The exception instance, if raised.
            exc_tb: The traceback, if raised.
        """
        ...


@runtime_checkable
class QueueStatus[T, U, R](QueueLifecycle[T, U, R], Protocol):
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
        ...


@runtime_checkable
class QueueInterface[T, U, R](
    QueueStatus[T, U, R],
    QueueSyncOps[T, U, R],
    Protocol,
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
