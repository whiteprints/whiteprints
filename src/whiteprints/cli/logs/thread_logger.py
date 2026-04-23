# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread-based structured logging listener for Whiteprints.

This module launches background threads to consume structured log records
from `queue.Queue` instances. These records are dispatched to sink handlers
configured for the logger — bypassing any `QueueHandler` indirection.

Thread loggers are ideal for:

- I/O-bound logging pipelines (e.g. network telemetry).
- Performance-sensitive paths that avoid thread spawn overhead.
- Ephemeral or test-time CLI contexts where multiprocessing is overkill.

Architecture:

- Each logger is keyed by a name of the form: 'worker_thread_<label>'
- The queue is thread-local and auto-registered via `ContextThreadQueue`.
- Each logging thread is represented as a `ThreadWorker`: a `threading.Thread`,
  stop event, death event, drained event, and exception queue.
- Graceful shutdown is coordinated via `atexit` and deferred signal handling.

Guarantees:

- Sink handlers (`StreamHandler`, `FileHandler`, etc.) are required.
- If no sinks are attached to a logger, a `NoSinkHandlerError` is raised
  and escalated via SIGTERM.
- All fatal exceptions are sent to the parent thread and flushed via
  `_monitor_death_thread`.
- Leftover log records are flushed to the emergency logger at shutdown.

This model mirrors the process-based logging system but operates entirely
within the same process using threads for lighter-weight concurrency.
"""

from collections.abc import Callable
from functools import cached_property, partial
from logging import Handler, LogRecord
from logging.handlers import QueueHandler, QueueListener
from queue import Queue as ThreadQueue
from threading import Event as ThreadEvent
from threading import Lock
from types import MappingProxyType
from typing import NamedTuple, override

from whiteprints.cli.logs import Logging
from whiteprints.cli.logs.logging_exceptions import SpawnLoggerWorkerError
from whiteprints.cli.logs.thread_logger_monitor import (
    DrainQueues,
    Thread,
    ThreadEvents,
    ThreadWorker,
    monitor_death_thread,
    shutdown_thread,
)
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.logs.handlers import ContextThreadQueue
from whiteprints.logs.logs_interface import Daemon
from whiteprints.signals_handler import DelaySignals


__all__ = [
    "shutdown_all_threads",
    "spawn_logging_thread",
]
"""Public module attributes."""


_LOGGING_THREADS: dict[str, ThreadWorker] = {}
"""Internal thread worker registry keyed by queue name."""

_LOGGING_THREADS_LOCK = Lock()
"""Thread-safe lock guarding access to `_LOGGING_THREADS`."""


def _set_thread_worker(name: str, worker: ThreadWorker) -> None:
    """Register a thread worker under a queue name.

    Ensures thread-safe access to the internal registry `_LOGGING_THREADS`.

    Args:
        name: Queue name used as the registry key.
        worker: The `ThreadWorker` instance managing the listener thread.
    """
    with _LOGGING_THREADS_LOCK:
        _LOGGING_THREADS[name] = worker


def get_all_thread_workers() -> MappingProxyType[str, ThreadWorker]:
    """Return a read-only snapshot of all active thread workers.

    Provides thread-safe access to the internal `_LOGGING_THREADS` registry,
    exposing currently running `ThreadWorker` instances keyed by queue name.

    Returns:
        A `MappingProxyType` containing all registered thread workers.
    """
    with _LOGGING_THREADS_LOCK:
        return MappingProxyType(_LOGGING_THREADS)


def extract_thread_sink_handlers(
    logging_instance: Logging,
) -> dict[str, list[Handler]]:
    """Collect all sink handlers for registered thread loggers.

    Filters out `QueueHandler` instances to isolate terminal sinks
    (e.g., `StreamHandler`, `FileHandler`) for each logger tied to
    a known thread-based queue.

    Args:
        logging_instance: The structured `Logging` system singleton.

    Returns:
        A mapping of logger names to their list of attached sink handlers.

    Note:
        This function is used by listener threads to reconstruct sink routes.
        If a logger has no non-QueueHandler, a fatal setup error will occur.
    """
    result: dict[str, list[Handler]] = {}
    for name in import_lazy_project("logs.logs_queue").get_all_thread_queues():
        logger = logging_instance.get_logger(name)
        sink_handlers = [
            h for h in logger.handlers if not isinstance(h, QueueHandler)
        ]
        if sink_handlers:
            result[name or ""] = sink_handlers

    return result


class _RecordsQueue(NamedTuple):
    """Named queue container for thread-based log listeners.

    This structure bundles a thread-safe `LogRecord` queue with a unique
    name identifier. It is used to pass structured logging queues to
    listener threads, enabling traceability and disambiguation
    across multithreaded environments.

    Attributes:
        name:   Canonical name of the queue (e.g., 'worker_thread_main').
        queue:  Thread-safe queue carrying `LogRecord` instances.
    """

    name: str
    queue: ThreadQueue[LogRecord]


class InstrumentedQueueListener(QueueListener):
    """QueueListener subclass that adds instrumentation to each LogRecord.

    Adds:
        - `dequeued_wall_time`: Time (in seconds since epoch) when the record
          was dequeued.
        - `queue_size`: Number of items remaining in the queue immediately
          after dequeue, or `None` if unavailable.

    These fields help diagnose logging delays and queue pressure in real time.
    """

    @cached_property
    def qsize(self) -> Callable[[], int | None]:
        """Return the queue's `qsize()` method or a safe fallback.

        This accessor returns a callable that, when invoked, returns the
        current queue size — i.e., the number of items left in the queue. If
        the queue does not implement `qsize()` (e.g., on certain platforms or
        custom queues), a fallback function is returned that always returns
        `None`.

        Returns:
            A callable that returns the queue size as an integer, or `None` if
            unavailable.
        """
        return getattr(self.queue, "qsize", lambda: None)

    @override
    def dequeue(  # type: ignore[override]
        self, block: bool
    ) -> LogRecord | None:
        # NOTE: Python's stdlib `QueueListener.dequeue` is incorrectly typed in
        # the `.pyi` stub as always returning `LogRecord`, but in reality it
        # may return a sentinel (`None`).
        record = super().dequeue(block=block)
        if record is None:  # type: ignore[unreachable]
            return None

        record.dequeued_wall_time = import_lazy("time").time()
        record.queue_size = self.qsize()
        return record


def _setup_listener(
    logging_instance: Logging,
    logger_name: str,
    records: _RecordsQueue,
    exception_queue: ThreadQueue[BaseException],
) -> InstrumentedQueueListener | None:
    """Initialize logger, handlers, and queue listener.

    Logs startup metadata and checks that the logger has configured sinks
    (i.e., non-QueueHandler handlers). If the logger is misconfigured, pushes
    an exception to the parent and shuts down the queue.

    Args:
        logging_instance: Logging system configured by parent.
        logger_name: Logger to resolve from the system.
        records: Queue and name used for log transmission.
        exception_queue: Queue to communicate fatal setup errors.

    Returns:
        A `QueueListener` instance if setup succeeded, else `None`.
    """
    sink_loggers = extract_thread_sink_handlers(logging_instance)
    if logger_name not in sink_loggers:
        with DelaySignals():
            exception_queue.put_nowait(
                import_lazy_project("logs.logs_queue").NoSinkHandlerError(
                    logger_name, records.name
                )
            )

        return None

    logger = logging_instance.get_logger(logger_name)
    logger.info(
        "Logger worker started",
        extra={
            "logger_name": logger_name,
            "logs_queue": records.queue,
        },
    )
    return InstrumentedQueueListener(records.queue, *sink_loggers[logger_name])


def _start_listener_with_polling(
    listener: QueueListener,
    events: ThreadEvents,
    idle_time: float,
) -> None:
    """Start the listener and poll for stop condition.

    The polling loop defers signals only during `event.wait()` calls.
    Signals are treated after each poll tick to allow graceful exits.

    Args:
        listener: The QueueListener to manage.
        events: Synchronization events for stop and death signaling.
        idle_time: Duration to wait between poll cycles.
    """
    listener.start()
    events.active.set()
    try:
        while not events.stop.is_set():
            events.healthcheck.set()
            events.stop.wait(idle_time)
    except (KeyboardInterrupt, InterruptedError):
        return


def _run_listener(
    listener: QueueListener,
    events: ThreadEvents,
    exception_queue: ThreadQueue[BaseException],
    idle_time: float = 0.1,
) -> None:
    """Run listener lifecycle with hardened signal-safe polling.

    Starts the listener, polls for stop condition in a hardened loop, and
    ensures proper teardown. Signals like SIGINT and SIGTERM are deferred
    during blocking waits using `DelaySignals`, allowing safe interruption
    outside critical sections.

    Args:
        listener: Active QueueListener consuming log records.
        events: Synchronization events for stop and death signaling.
        exception_queue: Queue used to send fatal listener errors to parent.
        idle_time: Polling interval in seconds between stop checks.
    """
    try:
        _start_listener_with_polling(listener, events, idle_time)
    except (OSError, BrokenPipeError, EOFError) as error:
        with DelaySignals():
            exception_queue.put_nowait(error)
    finally:
        listener.stop()


def _listener_teardown(
    listener: QueueListener,
    records: _RecordsQueue,
    drain_queues: DrainQueues,
    events: ThreadEvents,
) -> None:
    """Teardown logic for the listener thread — always runs.

    This function ensures proper shutdown of the logging thread. It sets
    lifecycle flags, flushes any remaining log records to the drain queue,
    and stops the listener.

    Args:
        listener: The active `QueueListener` instance to stop.
        records: The queue wrapper containing the thread's log queue.
        drain_queues: Queues used for emergency draining of records and errors.
        events: Synchronization events indicating thread status and shutdown.
    """
    events.death.set()
    events.active.clear()
    with DelaySignals():
        while not records.queue.empty():
            drain_queues.records.put_nowait(records.queue.get_nowait())

        events.drained.set()
        records.queue.join()

    listener.stop()


def _listener_thread(
    logging_instance: Logging,
    logger_name: str,
    records: _RecordsQueue,
    drain_queues: DrainQueues,
    events: ThreadEvents,
) -> None:
    """Entry point for thread-based logging listener.

    This function is executed in the listener thread. It sets up a
    `QueueListener` tied to the given queue and logger name, and then
    waits until signaled to shut down via `stop_event`.

    On startup failure, it pushes exceptions to the parent via
    `exception_queue`. On shutdown, it transfers any remaining log records
    into the `drain_queue` so they can be handled by the parent's
    emergency logger.

    Args:
        logging_instance: Logging system singleton preconfigured in the parent.
        logger_name: Name of the logger whose sinks will receive records.
        records: Queue name and structured `LogRecord` queue.
        drain_queues: Queues for error and record draining.
        events: Synchronization events for stop and death signaling.
    """
    listener = None
    try:
        listener = _setup_listener(
            logging_instance, logger_name, records, drain_queues.exceptions
        )
        if listener is None:
            events.death.set()
            events.drained.set()
            return

        _run_listener(listener, events, drain_queues.exceptions)
    finally:
        if listener is not None:
            _listener_teardown(listener, records, drain_queues, events)


def shutdown_all_threads(patience: float, timeout: float) -> None:
    """Gracefully terminate all active thread-based logging workers.

    This function iterates over all registered `ThreadWorker` instances
    and attempts to shut each one down cleanly using the provided
    `patience` and `timeout` values. Shutdown is cooperative via a stop
    event, followed by a timed join loop.

    Args:
        patience: Maximum total duration (in seconds) to wait for each
                  worker to exit before proceeding to the next.
        timeout: Polling interval (in seconds) between join attempts.

    Note:
        This is typically invoked at exit or upon receiving termination
        signals to ensure that child threades release resources and
        flush log queues without abrupt termination.
    """
    for thread_worker in get_all_thread_workers().values():
        shutdown_thread(
            thread_worker,
            patience,
            timeout,
        )


class _ThreadQueueBundle(NamedTuple):
    """Grouped queue-related resources for the thread-based logger system.

    Attributes:
        name: Canonical queue name (used for thread labels).
        context: Thread-local queue context wrapper.
        drain: Aggregated log queues for records and exceptions.
    """

    name: str
    context: ContextThreadQueue
    drain: DrainQueues


class _ThreadControl(NamedTuple):
    """Grouped control parameters for thread lifecycle.

    Attributes:
        events: Thread lifecycle signaling events.
        daemon: Daemon policy for worker and monitor threads.
        patience: Graceful shutdown timeout in seconds.
        timeout: Poll interval for shutdown joins and health checks.
    """

    events: ThreadEvents
    daemon: Daemon
    patience: float
    timeout: float


class _ThreadLoggerSetup(NamedTuple):
    """Composite setup for launching the thread-based logger.

    Attributes:
        queues: Thread queue-related components.
        control: Thread lifecycle configuration.
        logging_instance: The configured logging singleton.
    """

    queues: _ThreadQueueBundle
    control: _ThreadControl
    logging_instance: Logging


def start_logger_thread(setup: _ThreadLoggerSetup) -> ThreadWorker:
    """Start the structured logging thread.

    This thread consumes records from a queue and dispatches them to
    standard handlers.

    Also registers a shutdown hook for safe termination.

    Args:
        setup: Bundled logger setup for thread-based logging.

    Returns:
        A `ThreadWorker` instance representing the thread lifecycle.

    Raises:
        SpawnLoggerWorkerError: If the logger thread fails to start.
    """
    logger_thread = Thread(
        target=_listener_thread,
        args=(
            setup.logging_instance,
            setup.queues.name,
            _RecordsQueue(setup.queues.name, setup.queues.context.queue),
            setup.queues.drain,
            setup.control.events,
        ),
        name=setup.queues.name,
        daemon=setup.control.daemon.worker,
    )

    thread_worker = ThreadWorker(
        logger_thread,
        import_lazy("os").getpid(),
        setup.control.events,
        setup.queues.drain.exceptions,
        setup.queues.drain.records,
    )

    logger_terminator = partial(
        shutdown_thread,
        thread_worker,
        setup.control.patience,
        setup.control.timeout,
    )
    import_lazy_project("exit_codes").ExitCode.atexit(logger_terminator)

    try:
        logger_thread.start()
    except OSError as e:
        raise SpawnLoggerWorkerError from e

    _set_thread_worker(setup.queues.name, thread_worker)
    return thread_worker


def start_logger_thread_monitor(
    queues: _ThreadQueueBundle,
    control: _ThreadControl,
    worker: ThreadWorker,
) -> None:
    """Start a watchdog thread to monitor the logger thread.

    Args:
        queues: Drain bundle containing record and exception queues.
        control: Lifecycle and shutdown configuration.
        worker: The thread-based logger instance to supervise.

    Raises:
        SpawnLoggerWorkerError: If monitor thread fails to start.
    """
    monitor = Thread(
        target=monitor_death_thread,
        args=(queues.drain, worker, control.patience, control.timeout),
        name=f"{queues.name}_monitor",
        daemon=control.daemon.monitor,
    )

    try:
        monitor.start()
    except OSError as e:
        raise SpawnLoggerWorkerError from e

    import_lazy_project("exit_codes").ExitCode.atexit(monitor.join)


def spawn_logging_thread(
    queue_name: str,
    context_queue: ContextThreadQueue,
    patience: float,
    timeout: float,
    daemon: Daemon,
) -> None:
    """High-level initializer for thread-based structured logging.

    Wires together:
      - Queue instantiation and cleanup
      - Logger thread startup
      - Watchdog monitor
      - Daemon policy handling

    Args:
        queue_name: Canonical name of the logging queue.
        context_queue: Thread-based queue and context wrapper.
        patience: Grace period for shutdowns.
        timeout: Polling interval during joins and death checks.
        daemon: Daemon flags for worker and monitor.
    """
    with DelaySignals():
        logging_instance = import_lazy_project("cli.logs").LOGGING

        exception_queue = ThreadQueue[BaseException]()
        records_queue = ThreadQueue[LogRecord]()
        drain = DrainQueues(exception_queue, records_queue)

        for q in (exception_queue, records_queue):
            import_lazy_project("exit_codes").ExitCode.atexit(
                partial(
                    import_lazy_project(
                        "logs.logs_queue"
                    ).terminate_thread_queue,
                    q,
                )
            )

        events = ThreadEvents(
            ThreadEvent(),
            ThreadEvent(),
            ThreadEvent(),
            ThreadEvent(),
            ThreadEvent(),
        )

        queues = _ThreadQueueBundle(queue_name, context_queue, drain)
        control = _ThreadControl(events, daemon, patience, timeout)
        setup = _ThreadLoggerSetup(queues, control, logging_instance)

        thread_worker = start_logger_thread(setup)
        start_logger_thread_monitor(queues, control, thread_worker)
