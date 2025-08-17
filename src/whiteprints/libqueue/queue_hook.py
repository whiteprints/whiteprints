# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue Hooks.

Hooks provide lifecycle callbacks and contextual wrappers for key queue
operations. A hook is attached to a queue instance and may inspect,
modify, or react to queue events like put/get, task completion, or
shutdown.

Note:
    The before_put, after_put, before_get, and after_get hooks are invoked
    while the internal queue lock is held. Therefore, they must avoid blocking
    behavior, long-running computations, or any operation that could delay
    other threads or processes. These hooks are intended for minimal,
    lock-safe instrumentation only. Misuse may significantly degrade
    throughput and introduce contention under high concurrency.

    It is valid to use these hooks for instrumentation purposes that
    require consistent queue state under lock—for example:

        - Reading or sampling the queue size
        - Attaching lightweight metadata to items
        - Tracking timestamps or simple counters

    However, avoid using these hooks for operations such as:

        - File or network I/O
        - Logging through blocking handlers
        - Any logic with significant or unpredictable runtime

    These hooks are not intended for general preprocessing or data
    transformation pipelines. Their primary use is safe and minimal
    instrumentation that benefits from executing under the queue's
    lock.
"""

from collections.abc import Callable
from functools import partial
from typing import (
    Final,
    TypedDict,
    cast,
    override,
)

from whiteprints.lazy_import import import_lazy
from whiteprints.libqueue import SHUTDOWN, BaseSentinel
from whiteprints.libqueue.queue_exceptions import ShutDownError
from whiteprints.libqueue.queue_interface import QueueHook, QueueInterface


__all__: Final = [
    "BaseQueueHook",
    "MergedHook",
    "NoQueueHook",
]
"""Public module attributes."""


class BaseQueueHook[T, U, R](QueueHook[T, U, R]):
    """Base class for implementing QueueHook with default no-op behavior.

    This class provides a structured foundation for custom queue hook
    implementations. It implements the full `QueueHook` protocol with
    default no-op methods and stores a reference to the associated queue.

    Subclassing `BaseQueueHook` is the preferred way to create hook logic,
    as it offers a consistent and safe interface for lifecycle callbacks.

    Generic Parameters:
        T: The type accepted by the public `put()` interface.
        U: The internal representation stored in the queue (after
            `before_put()`).
        R: The return type produced by `get()` (after `after_get()`).
    """

    @classmethod
    def via[V](
        cls,
        other: (type[QueueHook[U, V, U]] | Callable[[], QueueHook[U, V, U]]),
    ) -> Callable[[], QueueHook[T, V, R]]:
        """Chains this hook with another, returning a composed hook class.

        This method enables sequential hook composition using the `+` operator.
        It returns a `MergedHook` that first applies this hook's `before_put()`
        and then the other hook's `before_put()`. On retrieval, the other
        hook's `after_get()` is applied first, followed by this hook's
        `after_get()`.

        Hook composition order:
            - `put()` path: self.before_put → other.before_put
            - `get()` path: other.after_get → self.after_get

        Type flow:
            - A: T → U (put), U → R (get)
            - B: U → V (put), V → U (get)
            - Composed: T → V (put), V → R (get)

        This is equivalent to `hook_merger(A, B)`, but allows cleaner
        chaining syntax. The composed class preserves static typing.

        Args:
            other: A hook class to apply after this one during `put()` and
                before during `get()`.

        Returns:
            A new hook class combining both in sequence.
        """
        return partial(MergedHook, cls(), other())

    def __add__[V](self, other: QueueHook[U, V, U]) -> QueueHook[T, V, R]:
        """Creates a composed hook by chaining this hook with another.

        This method enables sequential hook composition using the `+` operator.
        It returns a `MergedHook` that first applies this hook's `before_put()`
        and then the other hook's `before_put()`. On retrieval, the other
        hook's `after_get()` is applied first, followed by this hook's
        `after_get()`.

        Hook composition order:
            - `put()` path: self.before_put → other.before_put
            - `get()` path: other.after_get → self.after_get

        Type flow:
            - self: T → U (put), U → R (get)
            - other: U → V (put), V → U (get)
            - result: T → V (put), V → R (get)

        Args:
            other: A hook instance to compose after this one during `put()` and
                   before this one during `get()`.

        Returns:
            A new `MergedHook` representing the composed behavior.
        """
        return MergedHook(self, other)

    def __getstate__(self) -> None:
        """Support pickling of generic hook types.

        Python's `multiprocessing` requires objects to be picklable when
        passed between processes. However, generic classes like
        `BaseQueueHook[T, U, R]` cannot be automatically pickled due to the
        way generics are implemented using `typing`.

        This method returns a stateless representation, allowing derived hooks
        to be safely passed across process boundaries without raising
        `PicklingError`.

        Returns:
            None, indicating that the hook has no state to serialize.
        """

    def __setstate__(self, state: None) -> None:
        """Restores a stateless hook during unpickling.

        Since `BaseQueueHook` and its derivatives are typically stateless,
        this method simply ensures compatibility with Python's pickling
        protocol without restoring any actual data.

        Required to avoid pickling errors in `multiprocessing`.

        Args:
            state: Ignored (only present for signature compatibility).
        """

    @staticmethod
    def on_shutdown_sentinel[TQ, UQ, RQ](
        exception: Exception | None = None,
    ) -> ShutDownError:
        new_exception = ShutDownError()
        if exception is not None:
            new_exception.__cause__ = exception

        return new_exception

    @override
    def on_get_sentinel[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
        sentinel: BaseSentinel,
        exception: Exception | None = None,
    ) -> Exception:
        """Converts a sentinel into an exception to raise.

        This is called when a sentinel is retrieved from the queue and
        not handled internally. The returned exception is raised by the
        queue backend.

        Args:
            queue: The hooked queue.
            sentinel: The sentinel instance retrieved.
            exception: An optional inner exception (from a prior hook).

        Returns:
            A new exception, typically wrapping or replacing the input.
        """
        if sentinel is SHUTDOWN:
            return self.on_shutdown_sentinel(exception)

        new_exception = NotImplementedError()
        if exception is not None:
            new_exception.__cause__ = exception

        return new_exception


class _MergedHookState[T, U, V, R](TypedDict):
    """Internal pickle state for MergedHook.

    This structure captures the serialized state of a MergedHook instance,
    enabling cross-process transmission (e.g., with multiprocessing). Since
    generic parameters are not preserved during pickling, we manually store
    the composed hooks.

    Attributes:
        hook: The outer hook. It is applied first on put operations and
            last on get operations. Responsible for external behavior.
        via_hook: The inner hook. It is applied after `hook` on put and
            before `hook` on get. Typically used for wrapping or adapting
            the intermediate item representation.
    """

    hook: QueueHook[T, U, R]
    via_hook: QueueHook[U, V, U]


class MergedHook[T, U, V, R](QueueHook[T, V, R]):
    """Sequential composition of two queue hooks.

    `MergedHook` combines two `QueueHook` instances — one outer and one
    inner — into a single hook that can be attached to a queue. This enables
    modular instrumentation without tightly coupling behaviors.

    Hook composition follows a strict and well-defined order that preserves
    logical consistency and symmetry:

      • On `put()`:
          1. Outer hook (`hook`) runs `prepare_put`
          2. Inner hook (`via_hook`) runs `prepare_put`
          3. Inner hook runs `inlock_pre_put` / `inlock_post_put`
          4. Outer hook runs `inlock_pre_put` / `inlock_post_put`
          5. Inner hook runs `finalize_put`
          6. Outer hook runs `finalize_put`

        This ordering allows the outer hook to preprocess the public `put()`
        item and postprocess the final outcome — effectively bracketing the
        entire enqueue lifecycle. The inner hook focuses on internal
        transformations or state updates.

      • On `get()`:
          1. Outer hook runs `prepare_get`
          2. Inner hook runs `prepare_get`
          3. Inner hook runs `inlock_pre_get` / `inlock_post_get`
          4. Outer hook runs `inlock_pre_get` / `inlock_post_get`
          5. Inner hook runs `finalize_get`
          6. Outer hook runs `finalize_get`

        This mirrors the same lifecycle structure as `put()`, ensuring
        compositional symmetry.

    The hook stack uses thread-local storage to track intermediate items
    between outer and inner `prepare_put` and `finalize_put` calls. This
    avoids shared state and guarantees safety under concurrent access.

    Note:
        - The composition assumes that the inner hook transforms U → V on put,
          and V → U on get.
        - The outer hook operates on public types: T → U (put), U → R (get).
        - Hooks are always executed in order for `prepare_*`, and in reverse
          for `finalize_*`, forming a nested logical flow.

    Attributes:
        hook:
            The outer hook (user-facing). It runs first on `put()` and last
            on `get()`.
        via_hook:
            The inner hook (internal-facing). It runs second on `put()` and
            first on `get()`.
        _local:
            Thread-local stack to store intermediate prepared values between
            `prepare_put()` and `finalize_put()`.
    """

    __slots__ = ("_local", "hook", "via_hook")

    def _init_threadlocal(self) -> None:
        """Initializes thread-local storage for prepare/finalize tracking.

        This storage allows intermediate values produced by `prepare_put`
        to be passed back to `finalize_put`, maintaining thread safety.
        """
        threading = import_lazy("threading")
        self._local = threading.local()
        self._local.stack = []

    def __init__(
        self,
        hook: QueueHook[T, U, R],
        via_hook: QueueHook[U, V, U],
    ) -> None:
        """Initializes both inner hooks using the shared queue.

        Args:
            hook: Hook from T → U (put) and U → R (get).
            via_hook: Hook from U → V (put) and V → U (get).
        """
        self.hook = hook
        self.via_hook = via_hook
        self._init_threadlocal()

    def after_init[TQ, VQ, RQ](
        self, queue: QueueInterface[TQ, VQ, RQ]
    ) -> None:
        """Run both hooks' post-initialization logic.

        This is called once after the queue is fully constructed.

        Args:
            queue: the hooked queue.
        """
        self.via_hook.after_init(queue)
        self.hook.after_init(queue)

    def before_shutdown[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
    ) -> None:
        """Notify both hooks before shutdown begins.

        Outer hook is notified first, then inner.

        Args:
            queue: the hooked queue.
        """
        self.hook.before_shutdown(queue)
        self.via_hook.before_shutdown(queue)

    def after_shutdown[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
    ) -> None:
        """Notify both hooks after shutdown completes.

        Inner hook is notified first, then outer.

        Args:
            queue: the hooked queue.
        """
        self.via_hook.after_shutdown(queue)
        self.hook.after_shutdown(queue)

    def prepare_put[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
        item: T | BaseSentinel,
    ) -> V | BaseSentinel:
        """Transforms the public item before enqueueing.

        Applies `hook.prepare_put`, saves intermediate result, and
        passes it to `via_hook.prepare_put`.

        Args:
            queue: The hooked queue.
            item: Item passed to `put()`.

        Returns:
            Transformed item to store in the queue.
        """
        intermediate = self.hook.prepare_put(queue, item)
        self._local.stack.append(intermediate)
        return self.via_hook.prepare_put(queue, intermediate)

    def inlock_pre_put[TQ, VQ, RQ](
        self, queue: QueueInterface[TQ, VQ, RQ], item: V | BaseSentinel
    ) -> None:
        """Runs locked pre-put logic in reverse order.

        Inner hook receives the final item; outer gets the original
        intermediate value from prepare_put.

        Args:
            queue: The hooked queue.
            item: Item stored in queue.
        """
        self.hook.inlock_pre_put(queue, self._local.stack[-1])
        self.via_hook.inlock_pre_put(queue, item)

    def inlock_post_put[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
        item: V | BaseSentinel,
    ) -> None:
        """Runs locked post-put logic in reverse order.

        This mirrors `inlock_pre_put`.

        Args:
            queue: The hooked queue.
            item: Item stored in queue.
        """
        self.via_hook.inlock_post_put(queue, item)
        self.hook.inlock_post_put(queue, self._local.stack[-1])

    def finalize_put[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
        item: V | BaseSentinel,
    ) -> None:
        """Completes the enqueue lifecycle in reverse order.

        Restores the intermediate item from prepare_put and passes it
        to the outer hook.

        Args:
            queue: The hooked queue.
            item: The item added to the queue.
        """
        self.via_hook.finalize_put(queue, item)
        self.hook.finalize_put(queue, self._local.stack.pop())

    def prepare_get[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
    ) -> None:
        """Calls both hooks' before_get handlers in order.

        Args:
            queue: the hooked queue.
        """
        self.hook.prepare_get(queue)
        self.via_hook.prepare_get(queue)

    def inlock_pre_get[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
    ) -> None:
        """Runs locked pre-get operations in order.

        The outer hook is called first, followed by the inner hook. These
        hooks run while the queue's lock is held and may coordinate state
        or instrumentation related to item retrieval.

        Args:
            queue: The hooked queue.
        """
        self.hook.inlock_pre_get(queue)
        self.via_hook.inlock_pre_get(queue)

    def inlock_post_get[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
    ) -> None:
        """Runs locked post-get operations in reverse order.

        The inner hook is called first, followed by the outer hook. These
        hooks run while the queue's lock is held and can be used for
        synchronized side-effects after an item is dequeued but before
        it's returned to the user.

        Args:
            queue: The hooked queue.
        """
        self.via_hook.inlock_post_get(queue)
        self.hook.inlock_post_get(queue)

    def finalize_get[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
        item: V,
    ) -> R:
        """Finalizes the get operation and returns the user-facing value.

        Applies `via_hook.finalize_get()` then `hook.finalize_get()`.

        Args:
            queue: The hooked queue.
            item: The raw item retrieved.

        Returns:
            The transformed item returned to the consumer.
        """
        result = self.via_hook.finalize_get(queue, item)
        return self.hook.finalize_get(queue, result)

    def on_get_sentinel[TQ, VQ, RQ](
        self,
        queue: QueueInterface[TQ, VQ, RQ],
        sentinel: BaseSentinel,
        exception: Exception | None = None,
    ) -> Exception:
        """Resolves a se_getntinel to an exception via both inner hooks.

        Calls h2 first (inner), then passes its result to h1 (outer).
        This allows the outer hook to refine or replace the inner
        exception.

        Args:
            queue: the hooked queue.
            sentinel: The sentinel retrieved from the queue.
            exception: An optional pre-existing exception to wrap.

        Returns:
            A final exception raised by the queue backend.

        Example:
            Exception chaining via h2.on_sentinel → h1.on_sentinel
        """
        return self.hook.on_get_sentinel(
            queue,
            sentinel,
            self.via_hook.on_get_sentinel(queue, sentinel, exception),
        )

    def __getstate__(self) -> _MergedHookState[T, U, V, R]:
        """Serialize internal state for multiprocessing pickling.

        This method is required to enable custom serialization of generic
        hook classes, which otherwise cannot be pickled due to unresolved
        type variables. It stores the inner and outer hooks explicitly.

        Returns:
            A dictionary capturing the essential internal state.
        """
        return _MergedHookState(
            hook=self.hook,
            via_hook=self.via_hook,
        )

    def __setstate__(self, state: _MergedHookState[T, U, V, R]) -> None:
        """Restore internal state from a pickled representation.

        This reinitializes the merged hook after deserialization,
        restoring both wrapped hooks and reinitializing thread-local
        storage.

        Args:
            state: The dictionary returned by `__getstate__()`.
        """
        self.hook = state["hook"]
        self.via_hook = state["via_hook"]
        self._init_threadlocal()


class NoQueueHook[T, U, R](BaseQueueHook[T, U, R]):
    """A no-op hook implementation that disables all queue instrumentation.

    This class is used to explicitly opt out of lifecycle hooks. It allows
    the queue implementation to dispatch to a lighter code path with no
    hook-related logic.

    When `NoQueueHook` is passed to the queue constructor, the queue
    optimizes away hook calls via internal dispatch (e.g., method binding),
    ensuring zero runtime overhead for disabled instrumentation.
    """

    @override
    def after_init[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked after the queue is fully initialized.

        No-op in this implementation.
        """

    @override
    def prepare_put[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
        item: T | BaseSentinel,
    ) -> U | BaseSentinel:
        """Hook invoked immediately before placing an item in the queue.

        In the no-op variant, returns the item unchanged.

        Args:
            queue: The associated queue instance.
            item: The item (or sentinel) to enqueue.

        Returns:
            The unchanged item, cast to the internal queue type.
        """
        return cast("U", item)

    @override
    def inlock_pre_put[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
        item: U | BaseSentinel,
    ) -> None:
        """Hook invoked immediately after an item is stored in the queue.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
            item: The item or sentinel just stored.
        """

    @override
    def inlock_post_put[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
        item: U | BaseSentinel,
    ) -> None:
        """Hook invoked immediately after retrieving an item from the queue.

        In the no-op variant, returns the item unchanged.

        Args:
            queue: The associated queue instance.
            item: The item retrieved from the queue.
        """

    @override
    def finalize_put[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
        item: U | BaseSentinel,
    ) -> None:
        """Hook invoked immediately after an item is stored in the queue.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
            item: The item or sentinel just stored.
        """

    @override
    def prepare_get[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked immediately before retrieving an item.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
        """

    @override
    def inlock_pre_get[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked immediately before an item is retrieved from the queue.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
        """

    @override
    def inlock_post_get[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked immediately after an item is retrieved from the queue.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
        """

    @override
    def finalize_get[TQ, UQ, RQ](
        self, queue: QueueInterface[TQ, UQ, RQ], item: U
    ) -> R:
        """Hook invoked immediately after retrieving an item from the queue.

        In the no-op variant, returns the item unchanged.

        Args:
            queue: The associated queue instance.
            item: The item retrieved from the queue.

        Returns:
            The unchanged item, cast to the public-facing return type.
        """
        return cast("R", item)

    @override
    def before_shutdown[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked before the queue shutdown begins.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
        """

    @override
    def after_shutdown[TQ, UQ, RQ](
        self,
        queue: QueueInterface[TQ, UQ, RQ],
    ) -> None:
        """Hook invoked after the queue shutdown completes.

        No-op in this implementation.

        Args:
            queue: The associated queue instance.
        """

    def __getstate__(self) -> None:
        """Support pickling for multiprocessing compatibility.

        Generic types like `NoQueueHook[T, U, R]` are not natively picklable
        due to the way Python's `typing` module creates runtime
        representations. This method ensures that the hook can be serialized
        and transferred between processes by reducing it to a stateless
        representation.

        Returns:
            None, indicating stateless serialization.
        """

    def __setstate__(self, state: None) -> None:
        """Restore a pickled no-op hook instance.

        Because `NoQueueHook` is stateless, this method simply reconstructs
        the instance with no stored data. Required to avoid pickling errors
        with generic class instantiation in `multiprocessing`.

        Args:
            state: Ignored. Only present for signature compatibility.
        """
