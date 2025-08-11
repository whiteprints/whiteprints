# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Manages subprocess-based logging listeners.

This module is responsible for spawning and coordinating logging subprocesses
that consume log records from multiprocessing queues and forward them to
non-queue-based sink handlers (e.g. file, stream). Each listener runs in its
own `multiprocessing.Process`, safely decoupling logging execution from the
main interpreter.

Responsibilities:
- Start a dedicated process for each structured logging queue.
- Ensure each process runs a `QueueListener` bound to sink handlers.
- Maintain a thread-safe registry of active subprocess loggers.
- Support cooperative shutdown via stop events and join semantics.
- Register exit hooks to flush and clean up queues.

This module does not handle crash monitoring or forced termination.
Those responsibilities are delegated to `process_logger_monitor`.
"""

from functools import partial
from logging import Handler, LogRecord
from logging.handlers import QueueHandler
from threading import Lock
from types import MappingProxyType
from typing import NamedTuple

from whiteprints.cli.logs import Logging
from whiteprints.cli.logs.logging_exceptions import SpawnLoggerWorkerError
from whiteprints.cli.logs.process_logger_monitor import (
    ProcessEvents,
    ProcessWorker,
)
from whiteprints.concurrency import reset_all_mutated_classvars
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libqueue.queue_protocol import QueueBackend, ShutDownError
from whiteprints.logs.logs_interface import Daemon
from whiteprints.signals_handler import DelaySignals


__all__ = [
    "shutdown_all_processes",
    "spawn_logging_process",
]
"""Public module attributes."""


_LOGGING_PROCESSES: dict[str, ProcessWorker] = {}
"""Internal process worker registry keyed by queue name."""

_LOGGING_PROCESSES_LOCK = Lock()
"""Thread-safe lock guarding access to `_LOGGING_PROCESSES`."""


def _set_process_worker(worker: ProcessWorker) -> None:
    """Register a process worker under a queue name.

    Ensures thread-safe access to the internal registry `_LOGGING_PROCESSES`.

    Args:
        name: Queue name used as the registry key.
        worker: The `ProcessWorker` instance managing the listener process.
    """
    with _LOGGING_PROCESSES_LOCK:
        _LOGGING_PROCESSES[worker.records.name] = worker


def get_all_process_workers() -> MappingProxyType[str, ProcessWorker]:
    """Return a read-only snapshot of all active process workers.

    Provides thread-safe access to the internal `_LOGGING_PROCESSES` registry,
    exposing currently running `ProcessWorker` instances keyed by queue name.

    Returns:
        A `MappingProxyType` containing all registered process workers.
    """
    with _LOGGING_PROCESSES_LOCK:
        return MappingProxyType(_LOGGING_PROCESSES)


def extract_process_sink_handlers(
    logging_instance: Logging,
) -> dict[str, list[Handler]]:
    """Collect all sink handlers for registered process loggers.

    Filters out `QueueHandler` instances to isolate final sinks (e.g.
    `StreamHandler`, `FileHandler`) for each logger tied to a known
    process-based queue.

    Args:
        logging_instance: The structured `Logging` system singleton.

    Returns:
        A mapping of logger names to their list of attached sink handlers.

    Note:
        This function is used by subprocesses to reconstruct sink routes.
        If a logger has no non-QueueHandler, a fatal setup error will occur.
    """
    result: dict[str, list[Handler]] = {}
    for name in import_lazy_project("logs.logs_queue").get_all_queue_names():
        logger = logging_instance.get_logger(name, env={})
        sink_handlers = [
            h for h in logger.handlers if not isinstance(h, QueueHandler)
        ]
        if sink_handlers:
            result[name or ""] = sink_handlers

    return result


class InstrumentedQueueListener:
    """QueueListener subclass that adds instrumentation to each LogRecord.

    Adds:
        - `dequeued_wall_time`: Time (in seconds since epoch) when the record
          was dequeued.
        - `queue_size`: Number of items remaining in the queue immediately
          after dequeue, or `None` if unavailable.

    These fields help diagnose logging delays and queue pressure in real time.
    """

    def __init__(
        self,
        queue: QueueBackend[LogRecord],
        *handlers: Handler,
        respect_handler_level: bool = False,
    ) -> None:
        """Initialise an instance with the specified queue and handlers."""
        self.queue = queue
        self.handlers = handlers
        self.respect_handler_level = respect_handler_level

    @classmethod
    def prepare(cls, record: LogRecord) -> LogRecord:
        """Prepare a record for handling.

        This method just returns the passed-in record. You may want to
        override this method if you need to do any custom marshalling or
        manipulation of the record before passing it to the handlers.

        Returns:
            the prepared record.
        """
        return record

    def handle(self, record: LogRecord) -> None:
        """Handle a record.

        This just loops through the handlers offering them the record
        to handle.
        """
        record = self.prepare(record)
        for handler in self.handlers:
            if not self.respect_handler_level:
                process = True
            else:
                process = record.levelno >= handler.level

            if process:
                handler.handle(record)

    def run(self) -> None:
        """Run the queue listener."""
        while True:
            with self.queue.qsize_lock():
                try:
                    record = self.queue.get(block=True)
                except ShutDownError:
                    break

                record.queue_size = self.queue.size

            record.dequeued_wall_time = import_lazy("time").time()
            self.handle(record)
            self.queue.task_done()


def _setup_listener(
    logging_instance: Logging,
    logger_name: str,
    records: QueueBackend[LogRecord],
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
    sink_loggers = extract_process_sink_handlers(logging_instance)
    if logger_name not in sink_loggers:
        raise import_lazy_project("logs.logs_queue").NoSinkHandlerError(
            logger_name, records.name
        )

    logger = logging_instance.get_logger(logger_name, env={})
    logger.info(
        "Logger worker started",
        extra={
            "logger_name": logger_name,
            "logs_queue": records.queue,
        },
    )
    return InstrumentedQueueListener(records.queue, *sink_loggers[logger_name])


def _start_listener_with_polling(listener: InstrumentedQueueListener) -> None:
    """Start the listener and poll for stop condition.

    The polling loop defers signals only during `event.wait()` calls.
    Signals are treated after each poll tick to allow graceful exits.

    Args:
        listener: The QueueListener to manage.
        events: Synchronization events controlling listener lifecycle state.
        idle_time: Duration to wait between poll cycles.
    """
    try:
        listener.run()
    except (KeyboardInterrupt, InterruptedError):
        return


def _run_listener(
    listener: InstrumentedQueueListener,
    events: ProcessEvents,
) -> None:
    """Run listener lifecycle with hardened signal-safe polling.

    Starts the listener, polls for stop condition in a hardened loop, and
    ensures proper teardown. Signals like SIGINT and SIGTERM are deferred
    during blocking waits using `DelaySignals`, allowing safe interruption
    outside critical sections.

    Args:
        listener: Active QueueListener consuming log records.
        events: Synchronization events controlling listener lifecycle state.
        exception_queue: Queue used to send fatal listener errors to parent.
        idle_time: Polling interval in seconds between stop checks.
    """
    try:
        _start_listener_with_polling(listener)
    finally:
        _listener_teardown(events)


def _listener_teardown(events: ProcessEvents) -> None:
    """Teardown logic for the listener process — always runs.

    Args:
        listener: The active `QueueListener` instance to stop.
        records: The `_RecordsQueue` instance providing the logging queue.
        drain_queues: Queues for flushing remaining logs and exceptions.
        events: Synchronization events controlling listener lifecycle state.
    """
    with DelaySignals():
        events.death.set()
        events.active.clear()


def _listener_process(
    logging_instance: Logging,
    records: ContextProcessQueue,
    events: ProcessEvents,
) -> None:
    """Entry point for subprocess-based logging listener.

    This function is executed in the child process. It sets up a logging
    `QueueListener` tied to the given queue and logger name, and then waits
    until signaled to shut down via `stop_event`.

    On startup failure, it pushes exceptions to the parent via
    `exception_queue`. On shutdown, it transfers any remaining log records
    into the `drain_queue` so they can be handled by the parent's emergency
    logger.

    Args:
        logging_instance: The logging system singleton from the parent process.
        logger_name: Name of the logger whose sinks will receive records.
        records: A `_RecordsQueue` containing the queue name and log queue.
        events: Synchronization events controlling the process lifecycle.
    """
    records.queue.cancel_join_thread()
    reset_all_mutated_classvars()
    listener = None
    print("HELLO FROM LOGGER", import_lazy("os").getpid())
    import signal

    print(
        "LOGGER SIGMASK", signal.pthread_sigmask(signal.SIG_BLOCK, [])
    )  # Shows current block
    try:
        listener = _setup_listener(
            logging_instance,
            records.name,
            records,
        )
        if listener is not None:
            _run_listener(listener, events)
    except KeyboardInterrupt:
        pass
    finally:
        _listener_teardown(events)
        print("LOGGER END")


def shutdown_all_processes() -> None:
    """Gracefully terminate all active process-based logging workers.

    This function iterates over all registered `ProcessWorker` instances
    and attempts to shut each one down cleanly using the provided
    `patience` and `timeout` values. Shutdown is cooperative via a stop
    event, followed by a timed join loop.

    Args:
        patience: Maximum total duration (in seconds) to wait for each
                  worker to exit before proceeding to the next.
        timeout: Polling interval (in seconds) between join attempts.

    Note:
        This is typically invoked at exit or upon receiving termination
        signals to ensure that child processes release resources and
        flush log queues without abrupt termination.
    """
    monitor = import_lazy_project("cli.logs.process_logger_monitor")
    for process_worker in get_all_process_workers().values():
        monitor.shutdown_process(process_worker)


class _ProcessControl(NamedTuple):
    """Grouped process control parameters for logger lifecycle.

    Attributes:
        events: Lifecycle signaling events for logger coordination.
        daemon: Daemon policy for worker and monitor.
        patience: Graceful shutdown timeout in seconds.
        timeout: Poll interval for shutdown joins and checks.
    """

    events: ProcessEvents
    daemon: Daemon


class _LoggerSetup(NamedTuple):
    """Composite setup structure for launching the logger process.

    Attributes:
        queues: Queue-related components (name, context, drains).
        control: Process control and lifecycle configuration.
        logging_instance: The configured logging system singleton.
    """

    records: ContextProcessQueue
    control: _ProcessControl
    logging_instance: Logging


def start_logger_process(setup: _LoggerSetup) -> ProcessWorker:
    """Start the structured logging subprocess.

    This creates a dedicated logger process responsible for dequeuing
    and dispatching log records from structured queues to their final
    output handlers.

    Also registers a shutdown hook for safe termination.

    Args:
        setup: All required components grouped in a `_LoggerSetup`.

    Returns:
        A `ProcessWorker` object representing the logger subprocess.

    Raises:
        SpawnLoggerWorkerError: If the process fails to start.
    """
    logger_process = setup.records.context.Process(
        target=_listener_process,
        args=(
            setup.logging_instance,
            setup.records,
            setup.control.events,
        ),
        name=f"process_logger__{setup.records.name}",
        daemon=setup.control.daemon.worker,
    )

    process_worker = ProcessWorker(
        logger_process,
        import_lazy("os").getpid(),
        setup.control.events,
        setup.records,
    )
    import_lazy_project("exit_codes").ExitCode.atexit(
        partial(
            import_lazy_project(
                "cli.logs.process_logger_monitor"
            ).shutdown_process,
            process_worker,
        )
    )

    try:
        print("STARTING LOGGER")
        logger_process.start()
    except OSError as os_error:
        raise SpawnLoggerWorkerError from os_error

    _set_process_worker(process_worker)
    return process_worker


def spawn_logging_process(
    context_queue: ContextProcessQueue,
    daemon: Daemon,
) -> None:
    """High-level initializer for structured logging subprocess and monitor.

    This wires together:
      - Queue registration and cleanup (via atexit)
      - Logger process instantiation and startup
      - Optional daemonization
      - Monitoring thread for subprocess health

    Args:
        context_queue: Context-aware queue wrapper used across processes.
        patience: Timeout duration for graceful shutdowns.
        timeout: Polling interval when joining subprocess or thread.
        daemon: Configuration for daemon mode of subprocess and monitor thread.
    """
    with DelaySignals():
        logging_instance = import_lazy_project("cli.logs").LOGGING
        context = context_queue.context

        events = ProcessEvents(
            context.Event(),
            context.Event(),
            context.Event(),
            context.Event(),
        )

        control = _ProcessControl(events, daemon)
        setup = _LoggerSetup(context_queue, control, logging_instance)

        process_worker = start_logger_process(setup)
        _set_process_worker(process_worker)
