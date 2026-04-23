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

from logging import LogRecord
from multiprocessing import Process
from multiprocessing.queues import JoinableQueue as ProcessQueue
from queue import Queue as ThreadQueue
from typing import NamedTuple

from whiteprints.concurrency import is_main_process, is_main_thread
from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.logs.handlers import (
    ContextProcessQueue,
    ContextThreadQueue,
)
from whiteprints.signals_handler import DelaySignals


__all__ = [
    "Daemon",
    "InvalidQueueNameError",
    "ProcessesStillActiveError",
    "ThreadsStillActiveError",
    "UnknownWorkerContextError",
    "terminate_logs_process_queue",
    "terminate_logs_thread_queue",
]
"""Public module attributes."""


class ProcessesStillActiveError(WhiteprintsError):
    """Raised when child processes are still alive during queue termination."""

    def __init__(self, processes: list[Process]) -> None:
        """Initialize the error with the list of active child processes.

        Args:
            processes: List of active multiprocessing.Process instances.
        """
        self.processes = processes
        self.count = len(processes)

        process_list = "\n".join(
            f"- {p.name} (pid={p.pid})" for p in processes
        )
        msg = _(
            "Cannot terminate log queue:"
            " {} child process(es) still active:\n{}"
        ).format(self.count, process_list)

        super().__init__(msg)


class ThreadsStillActiveError(WhiteprintsError):
    """Raised when threads are still alive during queue termination."""

    def __init__(self, count: int) -> None:
        """Initialize the error with the count of active threads.

        Args:
            count: Number of active threads.
        """
        self.count = count
        msg = _(
            "Cannot terminate thread log queue: {} thread(s) still active."
        ).format(count)
        super().__init__(msg)


class Daemon(NamedTuple):
    """Thread and process daemon mode configuration.

    This type controls whether both the logging worker and its
    crash monitor should run in daemon mode.

    Attributes:
        worker: Whether the main logging subprocess/thread is daemonized.
        monitor: Whether the crash monitor thread is daemonized.

    Notes:
        Daemon mode is a last-resort failsafe. When set to True, resources
        may be leaked or silently discarded if the interpreter exits
        unexpectedly.

        Unless your shutdown logic is fundamentally broken, keep both flags
        set to False. If you override this, you are disabling guarantees.

        I.e. set daemon.worker and daemon.monitor to False unless you know
        what you are doing.
    """

    worker: bool
    monitor: bool


class QueueAlreadyRegisteredError(WhiteprintsError):
    """Raised when a queue name has already been registered.

    Attributes:
        queue_name: The invalid queue name that triggered the exception.
    """

    def __init__(self, queue_name: str) -> None:
        """Initialize the exception.

        Args:
            queue_name: The queue name that failed validation.
        """
        super().__init__(_("Queue already registered: {}.").format(queue_name))
        self.queue_name = queue_name


class InvalidQueueNameError(WhiteprintsError):
    """Raised when a queue name does not follow the '<mode>_' pattern.

    Attributes:
        queue_name: The invalid queue name that triggered the exception.
    """

    def __init__(self, queue_name: str) -> None:
        """Initialize the exception.

        Args:
            queue_name: The queue name that failed validation.
        """
        super().__init__(
            _(
                "Invalid queue name: {}.\n"
                "Valid queue names are prefixed with 'thread_',"
                " 'forkserver_', 'fork_' or 'spawn_'"
            ).format(queue_name)
        )
        self.queue_name = queue_name


class UnknownWorkerContextError(WhiteprintsError):
    """Raised when the worker mode is missing or unrecognized.

    Attributes:
        queue_name: The queue name used when extracting the context.
        mode: The extracted mode string, or None if parsing failed.
    """

    def __init__(self, queue_name: str, mode: str | None) -> None:
        """Initialize the exception.

        Args:
            queue_name: The queue name that caused the mode to be parsed.
            mode: The parsed mode, if any (e.g. 'foo' or None).
        """
        super().__init__(
            _(
                "Invalid worker mode: '{}' deduced from '{}'.\n"
                "It should be one of:"
                " ['spawn', 'forkserver', 'fork', 'thread']"
            ).format("thread" if mode is None else mode, queue_name)
        )
        self.queue_name = queue_name
        self.mode = mode


class NoSinkHandlerError(WhiteprintsError):
    """Raised when no sink handler is attached to the logger in the config.

    This typically occurs if a logger exists but has only a `QueueHandler`,
    and no final destination such as a `StreamHandler` or `FileHandler`.

    Attributes:
        queue_name: The queue name associated with the failed logger.
        logger_name: The logger name expected in the configuration.
    """

    def __init__(self, logger_name: str, queue_name: str) -> None:
        """Initialize the exception with missing sink handler context.

        Args:
            logger_name: The logger that should have at least one sink handler.
            queue_name: The name of the queue associated with the logger.
        """
        super().__init__(
            _(
                "No sink handler found for queue named: '{}'\n"
                "You should have in your config a logger named '{}'"
                " attached at least one non `QueueHandler`."
            ).format(
                queue_name,
                logger_name,
            )
        )
        self.queue_name = queue_name
        self.logger_name = logger_name

    def __reduce__(self) -> tuple[type, tuple[str, str]]:
        """Support pickling of the exception instance.

        Returns:
            A tuple used to reconstruct the object during unpickling.
        """
        with DelaySignals():
            return (self.__class__, (self.logger_name, self.queue_name))


def drain_logs_queue(
    logs_queue: (
        ProcessQueue[LogRecord | None] | ThreadQueue[LogRecord | None]
    ),
) -> None:
    logger = import_lazy_project("cli.logs").LOGGING.get_logger(
        sub="emergency",
        env={},
    )
    queue = import_lazy("queue")
    while True:
        try:
            record = logs_queue.get_nowait()
        except queue_module.Empty:
            print("SIZE", logs_queue.qsize())
            continue
        except Exception as e:
            print("!! ERROR from queue:", type(e), e)
            raise

        if record is None:
            print("NONE SENTINEL")
            #  logs_queue.task_done()
            break

        logger.handle(record)
        #  logs_queue.task_done()


def drain_logs(
    context_queue: ContextProcessQueue | ContextThreadQueue,
) -> None:
    drain_logs_queue(context_queue.queue)


def terminate_logs_process_queue(
    context_queue: ContextProcessQueue,
) -> None:
    if is_main_thread() and is_main_process():
        print("CLOSING QUEUE MAIN")
        alive_processes = import_lazy("multiprocessing").active_children()
        if len(alive_processes) > 0:
            raise ProcessesStillActiveError(alive_processes)

        print("DRAIN QUEUE MAIN")
        context_queue.queue.put(None)
        import threading

        for thread in threading.enumerate():
            print(f"{thread.name=}, {thread.ident=}, {thread.is_alive()=}")

        drain_logs(context_queue)
        print("DRAINING DONE", context_queue.queue.qsize())
        context_queue.queue.close()
        print("JOINING QUEUE THREAD", context_queue.queue.qsize())
        context_queue.queue.join_thread()
        #  print("JOINED QUEUE")
        #  getattr(context_queue.queue, "join", lambda: None)()
        print("CLOSING QUEUE MAIN DONE")


def terminate_logs_thread_queue(
    context_queue: ContextThreadQueue,
) -> None:
    with DelaySignals():
        if is_main_thread() and is_main_process():
            alive_count = import_lazy("threading").active_count()
            if alive_count > 0:
                raise ThreadsStillActiveError(alive_count)

            drain_logs(context_queue)
            context_queue.queue.join()
