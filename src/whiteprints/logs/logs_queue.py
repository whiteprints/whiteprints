# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging queue registry and dynamic dispatcher.

This module provides deterministic, thread-safe registration and access
to structured logging queues used across multiprocessing and multithreaded
contexts in Whiteprints.

Responsibilities:
  - Centralize all log queue creation, keyed by name.
  - Guarantee signal-safe, thread-safe, and fork-safe instantiation.
  - Enable lazy initialization before consumer binding (e.g., listeners).
  - Enforce name-based access and validation for diagnostic traceability.

Behavior:
  - Queue creation is guarded by `_QUEUE_LOCK` and wrapped in `DelaySignals`
    to defer SIGINT/SIGTERM during critical sections.
  - All queues are registered once per process and never overwritten.
  - Exit hooks via `ExitCode.atexit()` clean up process/thread queues.

Rationale:
  - Log queues must exist *before fork*, but consumers (QueueListeners) should
    be bound *after CLI config loads*. This separation ensures robustness
    under:
      - fork, exec, and multiprocessing modes
      - multi-threaded CLI entrypoints
      - early signal delivery or config fallback

  - Queue names are treated as stable interfaces—configurable, debuggable,
    and introspectable. If a logger has no sink handler, this module raises
    `NoSinkHandlerError` during listener startup.

Signal handling:
  - `DelaySignals` is used consistently around queue registration to avoid
    partial state or corrupted shared memory if a signal arrives mid-init.
  - Signals are deferred only during critical regions and replayed if
    necessary.

This module is the foundation of logging lifecycle orchestration. It does not
emit records or run listeners. It registers queues—nothing more, nothing less.
"""

from functools import partial
from threading import Event as ThreadEvent
from threading import Lock
from types import MappingProxyType
from typing import Final, NamedTuple

from whiteprints.concurrency import is_main_process
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.logs.handlers import (
    Context,
    ContextDummyQueue,
    ContextProcessQueue,
    ContextQueue,
    ContextThreadQueue,
)
from whiteprints.logs.logs_interface import (
    InvalidQueueNameError,
    QueueAlreadyRegisteredError,
    UnknownWorkerContextError,
)
from whiteprints.signals_handler import DelaySignals


__all__ = [
    "get_all_process_queues",
    "get_all_queue_names",
    "get_all_thread_queues",
    "get_process_queue",
    "get_queue",
    "get_thread_queue",
]
"""Public module attributes."""


_REQURED_QUEUE_PARTS: Final = 2


_CREATED_PROCESS_QUEUES: dict[str, ContextProcessQueue] = {}
"""All registered multiprocessing queues, keyed by normalized name."""

_CREATED_THREAD_QUEUES: dict[str, ContextThreadQueue] = {}
"""All registered thread-based queues, keyed by normalized name."""

_CREATED_QUEUE_NAMES: set[str] = set()
"""Shadow registry of queue names seen by subprocesses.

When a subprocess accesses a queue attribute via `__getattr__`, we
add its label here to track the expected set of queues without
creating them. This avoids the overhead and danger of initializing
real queues in child processes (e.g., double-forked pipes, duplicate
event loops, or signal collisions).

This set enables CLI tools and log diagnostics to reflect accurate
queue expectations across contexts—even when the real queues exist
only in the main process.

Used by:
    - `__getattr__` (in subprocesses)
    - `get_all_queue_names()` to expose a merged view
"""

_QUEUE_LOCK = Lock()
"""Thread-level mutex to protect lazy queue creation.

This lock ensures that queue registration is atomic and thread-safe
under CPython's GIL, and compatible with free-threaded interpreters.

It guards both registry dictionaries to avoid race conditions when
multiple threads attempt to initialize the same queue simultaneously.
"""


class QueueName(NamedTuple):
    mode: str
    label: str
    size: int | None


def unescape_queue_label(label: str) -> str:
    """Decode a queue label from escaped form to dotted form.

    This decoding reverses a simple escaping scheme:
      - Single underscores (`_`) are treated as dots (`.`)
      - Double underscores (`__`) are treated as literal underscores (`_`)

    This allows labels to safely represent dot-separated paths using only
    valid Python identifiers, such as those required in logging `ext://` paths.

    Args:
        label: The escaped label string to decode.

    Returns:
        A decoded label string where underscores have been mapped to
        dots and escaped underscores preserved.
    """
    return label.replace("__", "\0").replace("_", ".").replace("\0", "_")


def parse_queue_name(name: str) -> QueueName:
    """Parse a queue name of the form '<mode>_<label>[_q<size>]'.

    Raises:
        InvalidQueueNameError: the queue name is invalid.

    Returns:
        mode: The queue mode, e.g. 'spawn', 'forkserver', 'fork' or 'thread'
        label: The queue label, e.g. 'main'
        size: Optional int if '_q<size>' suffix is provided
    """
    prefix, sep, qpart = name.rpartition("_q")
    if sep and qpart.isdigit():
        size = int(qpart)
    else:
        prefix = name
        size = None

    parts = prefix.split("_", 1)
    if len(parts) != _REQURED_QUEUE_PARTS:
        raise InvalidQueueNameError(name)

    mode, raw_label = parts
    label = unescape_queue_label(raw_label)

    return QueueName(mode, label, size)


def get_process_queue(
    name: str, context: Context, *, maxsize: int = 0
) -> ContextProcessQueue:
    """Return or create a process-based logging queue.

    Args:
        name: Normalized queue name.
        maxsize: Queue maximum size.
        context: Optional pre-parsed context for efficiency.

    Returns:
        A `ContextProcessQueue` instance.
    """
    with DelaySignals(), _QUEUE_LOCK:
        if name in _CREATED_PROCESS_QUEUES:
            return _CREATED_PROCESS_QUEUES[name]

        queue = ContextProcessQueue(
            name,
            context.Queue(maxsize),
            maxsize,
            context.Event(),
            context,
        )
        import_lazy_project("exit_codes").ExitCode.atexit(
            partial(
                import_lazy_project(
                    "logs.logs_interface"
                ).terminate_logs_process_queue,
                queue,
            )
        )

        if name in _CREATED_PROCESS_QUEUES:
            raise QueueAlreadyRegisteredError(name)

        _CREATED_PROCESS_QUEUES[name] = queue
        return queue


def get_thread_queue(name: str, *, maxsize: int = 0) -> ContextThreadQueue:
    """Return or create a thread-based logging queue.

    Args:
        name: Normalized queue name.
        maxsize: Queue maximum size.
        context: Optional context (should be None for thread queues).

    Returns:
        A `ContextThreadQueue` instance.
    """
    with DelaySignals(), _QUEUE_LOCK:
        if name in _CREATED_THREAD_QUEUES:
            return _CREATED_THREAD_QUEUES[name]

        queue = ContextThreadQueue(
            name,
            import_lazy("queue").Queue(maxsize),
            maxsize,
            ThreadEvent(),
        )
        import_lazy_project("exit_codes").ExitCode.atexit(
            partial(
                import_lazy_project(
                    "logs.logs_interface"
                ).terminate_logs_thread_queue,
                queue,
            )
        )

        if name in _CREATED_THREAD_QUEUES:
            raise QueueAlreadyRegisteredError(name)

        _CREATED_THREAD_QUEUES[name] = queue
        return queue


def get_queue(name: str) -> ContextQueue:
    """Return a lazily initialized logging queue for the given name.

    Args:
        name: A string like 'worker_spawn_main' or 'worker_thread_telemetry'.

    Returns:
        A `ContextProcessQueue` or `ContextThreadQueue`.

    Raises:
        UnknownWorkerContextError: Unknown multiprocessing context.
    """
    mode, label, size = parse_queue_name(name)
    _CREATED_QUEUE_NAMES.add(label)
    with DelaySignals():
        match mode:
            case "thread":
                context = None
            case "spawn":
                context = import_lazy("multiprocessing").get_context(mode)
            case "forkserver":
                context = import_lazy("multiprocessing").get_context(mode)
            case "fork":
                context = import_lazy("multiprocessing").get_context(mode)
            case _:
                raise UnknownWorkerContextError(name, mode)

    if context is None:
        return get_thread_queue(label, maxsize=size or 0)

    return get_process_queue(label, context, maxsize=size or 0)


def get_all_process_queues() -> MappingProxyType[str, ContextProcessQueue]:
    """Return a thread-safe read-only view of all registered process queues."""
    with _QUEUE_LOCK:
        return MappingProxyType(_CREATED_PROCESS_QUEUES)


def get_all_thread_queues() -> MappingProxyType[str, ContextThreadQueue]:
    """Return a thread-safe read-only view of all registered thread queues."""
    with _QUEUE_LOCK:
        return MappingProxyType(_CREATED_THREAD_QUEUES)


def get_all_queue_names() -> frozenset[str]:
    return frozenset(_CREATED_QUEUE_NAMES)


def __getattr__(name: str) -> ContextQueue:
    """Dynamically resolve a logging queue by name.

    This function enables lazy access to structured log queues using
    attribute-style lookup (e.g., `logs_queue.spawn_main_q1000`). It is
    designed to support Python's `ext://...` resolution mechanism in logging
    configs.

    In the main process, this will instantiate and return a real logging queue
    using `get_queue(name)`. In spawned subprocesses, it returns a lightweight
    `ContextDummyQueue` placeholder to avoid redundant or unsafe queue
    creation.

    As a side effect, queue labels accessed in subprocesses are added to
    `_CREATED_QUEUE_NAMES` for diagnostic or validation use (e.g., verifying
    expected queues are declared even if not initialized).

    Args:
        name: A queue name in the form 'spawn_<label>' or
            'thread_<label>[_q<size>]'.

    Returns:
        A `ContextProcessQueue` or `ContextThreadQueue` in the main process,
        or a `ContextDummyQueue` in subprocesses.

    Raises:
        AttributeError: If the queue name is invalid or unsupported.
    """
    if not name.startswith(("spawn_", "thread_", "forkserver_", "fork_")):
        raise AttributeError(name)

    if is_main_process():
        return get_queue(name)

    queue_name = parse_queue_name(name)
    _CREATED_QUEUE_NAMES.add(queue_name.label)
    return ContextDummyQueue()
