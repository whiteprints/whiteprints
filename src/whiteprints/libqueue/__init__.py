# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue library.

A unified queue interface for threading and multiprocessing, designed with:

- Strict shutdown semantics via sentinels
- Full protocol-based typing
- Support for asyncio-compatible APIs (via run_in_executor)
- Unified interface across backends (Thread, Process)
- Exact, lock-protected size tracking (via qsize_lock)

Unlike `queue.Queue` and `multiprocessing.Queue`, this system allows:

- Explicit shutdown signaling (via `Sentinel` and `shutdown()`)
- Task accounting with `task_done()` and `join()` across processes
- Cleaner type safety and backend control
- Manual file descriptor management for process-safe communication

Built to offer clarity, safety, and control in structured concurrent systems.
"""

from collections.abc import Callable
from functools import cache
from typing import Any, Final, Self, cast

from whiteprints.lazy_import import import_lazy


__all__ = ["BaseSentinel", "ShutdownSentinel", "SkipSentinel", "is_noop"]


class BaseSentinel:
    """A picklable, globally unique shutdown marker.

    Sentinels are used to signal queue shutdown. They compare equal only to
    themselves and are safe to use across threads and processes.
    """

    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        """Returns True only if `other` is the same sentinel class.

        Uses strict type identity (`type(self) is type(other)`) to avoid
        accidental equality with subclasses or other similarly named types.

        Args:
            other: The object to compare.

        Returns:
            True if `other` is the same sentinel type, False otherwise.
        """
        return type(self) is type(other)

    def __hash__(self) -> int:
        """Returns a consistent hash based on the sentinel's type.

        Ensures Sentinel subclasses can be used safely in sets and as
        dictionary keys, with hash values aligned to strict equality
        (`type(self) is type(other)`).

        Returns:
            A type-based hash for the sentinel.
        """
        return hash(type(self))

    def __reduce__(self) -> tuple[type[Self], tuple[()]]:
        """Supports pickling by returning a factory and args.

        Ensures that unpickling always returns the same cached Sentinel.

        Returns:
            A tuple of (factory_function_name, arguments).
        """
        return (self.__class__, ())


class SkipSentinel(BaseSentinel):
    """A special sentinel that signals the queue to skip an item.

    When returned by a hook's `before_put()`, this sentinel instructs
    the queue backend to silently discard the item and avoid enqueuing it.

    Unlike a shutdown sentinel, `SkipSentinel` is not propagated to
    consumers. It is used internally to filter or collapse input
    before storage.

    This sentinel is safe to compare, store, and use across threads
    and processes.
    """


class ShutdownSentinel(BaseSentinel):
    """Sentinel indicating queue shutdown.

    When enqueued, signals that no more items will follow.
    Consumers receiving this sentinel should cleanly exit or begin
    shutdown procedures. It is propagated through the queue and
    should not be filtered or transformed by hooks.

    Unlike `SkipSentinel`, this is intended to be *seen* by consumers.
    """


def _noop() -> None:
    """A noop example."""


def _identity[T](x: T) -> T:
    """An identity example.

    Returns:
        The input x.
    """
    return x


def _trivial_embedding[U](x: object) -> object:
    """An trivial embedding example.

    Returns:
        The input x.
    """
    return cast("U", x)


def _normalize_function(f: Callable[..., Any]) -> str:
    instrs = import_lazy("dis").get_instructions(f)
    code: list[str] = []
    for i in instrs:
        if i.opname in {"LOAD_FAST", "STORE_FAST"}:
            code.append(f"{i.opname} <var>")
        elif i.opname == "LOAD_CONST" and isinstance(i.argval, str):
            code.append(f"{i.opname} <const>")
        elif i.opname == "LOAD_GLOBAL":
            code.append(f"{i.opname} {i.argval}")
        else:
            code.append(i.opname)

    return " ".join(code)


@cache
def _known_noop() -> set[str]:
    return {
        _normalize_function(_noop),
        _normalize_function(_identity),
        _normalize_function(_trivial_embedding),
    }


def is_noop(func: Callable[..., Any]) -> bool:
    """Detects whether a function is a no-op.

    This function checks if the bytecode of a function matches that of
    `lambda: None` or lambda x: x, considering only a minimal instruction
    footprint (typically up to 3 bytes).

    It is used to detect trivial hook implementations that can be skipped
    for performance reasons, such as `def f(): pass`, `return`, or `...`.

    Args:
        func: A function to inspect.

    Returns:
        True if the function is considered a no-op, False otherwise.
    """
    bytecode = _normalize_function(func)
    return bytecode in _known_noop()


SHUTDOWN: Final = ShutdownSentinel()
"""Global shutdown sentinel. Propagated to consumers to trigger exit."""

SKIP: Final = SkipSentinel()
"""Global skip marker used to suppress enqueue during before_put hook."""
