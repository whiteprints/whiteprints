# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging handlers."""

from functools import cached_property
from io import IOBase
from logging import Formatter, Handler, LogRecord
from logging.handlers import QueueHandler
from multiprocessing.context import (
    ForkContext,
    ForkServerContext,
    SpawnContext,
)
from multiprocessing.queues import JoinableQueue as ProcessQueue
from multiprocessing.synchronize import Event as ProcessEvent
from queue import Full, SimpleQueue
from queue import Queue as ThreadQueue
from threading import Event as ThreadEvent
from typing import Final, NamedTuple, override

from whiteprints.lazy_import import has_extra, import_lazy, import_lazy_project
from whiteprints.logs import use_struct_logs
from whiteprints.logs.logs_exceptions import LogRecordDroppedError


__all__: Final = [
    "Context",
    "ContextProcessQueue",
    "ContextThreadQueue",
    "StreamHandler",
]
"""Public module attributes."""


type Context = SpawnContext | ForkContext | ForkServerContext
"""Union of all multiprocessing contexts."""


class ContextDummyQueue(NamedTuple):
    """Placeholder queue returned in subprocesses to avoid re-initialization.

    This dummy object is returned by `__getattr__` when a logging queue
    is accessed from a subprocess, where real queue creation is disabled.

    It allows the queue attribute lookup to succeed without silently breaking
    logging setup, while ensuring subprocesses don't trigger shared memory or
    threading behavior they shouldn't own.

    Notes:
        - The dummy queue should never be used for actual `put()` operations.
        - It exists solely to make logging configs referencing ext:// paths
          not crash inside workers.
    """

    name: str = ""
    queue: SimpleQueue[LogRecord | None] = SimpleQueue()


class ContextProcessQueue(NamedTuple):
    """Tuple wrapping a multiprocessing log queue with its context.

    Attributes:
        queue: A `multiprocessing.Queue` instance for interprocess logging.
        context: The multiprocessing context used to create the queue
                 (e.g. 'spawn', 'forkserver').
    """

    name: str
    queue: ProcessQueue[LogRecord | None]
    maxsize: int
    stop_event: ProcessEvent
    context: Context


class ContextThreadQueue(NamedTuple):
    """Tuple wrapping a thread-based log queue.

    Attributes:
        queue: A `queue.Queue` instance used for intra-thread logging.
    """

    name: str
    queue: ThreadQueue[LogRecord | None]
    maxsize: int
    stop_event: ThreadEvent


type ContextQueue = (
    ContextProcessQueue | ContextThreadQueue | ContextDummyQueue
)
"""Union of queue containers: either a thread-local or process-based queue."""


class StreamHandler(Handler):
    """A stream handler.

    A logging handler that delegates to rich.logging.RichHandler if the 'rich'
    extra is installed, otherwise falls back to the standard
    logging.StreamHandler.

    This handler exposes a simplified, unified interface for most users:
        - The `stream` argument behaves exactly like logging.StreamHandler's
          `stream`.
        - Internally, if RichHandler is used, `stream` is converted to a
          `rich.console.Console` instance automatically.

    Advanced users may pass additional keyword arguments which are forwarded
    only to RichHandler. These kwargs have no effect if RichHandler is not
    available.
    """

    @override
    def __init__(
        self,
        stream: IOBase | None = None,
        rich_handler_params: dict[str, object] | None = None,
    ) -> None:
        """Create a StreamHandler instance.

        Args:
            stream: The output stream to write logs to (same format as
                logging.StreamHandler). This is the preferred way for typical
                usage.
            redactor: module
            rich_handler_params: Optional keyword arguments forwarded
                exclusively to RichHandler for advanced configuration (ignored
                if RichHandler is not used).
        """
        super().__init__()
        self.stream = stream
        self.rich_handler_params = rich_handler_params or {}

    @cached_property
    def _delegate(self) -> Handler:
        if has_extra("rich") and not use_struct_logs():
            rich_handler_params = dict(self.rich_handler_params.items())
            console = rich_handler_params.pop(
                "console",
                import_lazy("rich.console").Console(
                    file=self.stream,
                ),
            )

            if import_lazy_project("logs").use_struct_logs():
                rich_handler_params["rich_tracebacks"] = False

            return import_lazy("rich.logging").RichHandler(
                **rich_handler_params,
                console=console,
            )

        return import_lazy("logging").StreamHandler(self.stream)

    @override
    def emit(self, record: LogRecord) -> None:
        self._delegate.emit(record)

    @override
    def setFormatter(self, fmt: Formatter | None) -> None:
        super().setFormatter(fmt)
        self._delegate.setFormatter(fmt)

    @override
    def setLevel(self, level: str | int) -> None:
        super().setLevel(level)
        self._delegate.setLevel(level)


class SafeQueueHandler(QueueHandler):
    """QueueHandler that blocks and tracks enqueue timing.

    This handler extends `QueueHandler` to support blocking `put()` with retry
    logic and listener health checks. It is useful for preventing silent log
    loss when a queue is full.

    The handler optionally raises `LogRecordDroppedError` if a log record
    cannot be enqueued after retry attempts or the listener is unhealthy.

    Args:
        queue: Context-aware queue wrapper to which log records are sent.
        block: Whether to block if the queue is full.
        timeout: Optional total time in seconds to retry enqueue.
        patience: Duration to wait between enqueue retries.
        raise_on_dropped_logs: If True, propagate dropped log errors.

    Attributes:
        context_queue: Queue wrapper used for sending log records.
        block: Whether to block during enqueue.
        timeout: Total wait duration before giving up.
        patience: Time between each retry attempt.
        raise_on_dropped_logs: Whether dropped log errors are raised.
    """

    @override
    def __init__(
        self,
        queue: ContextQueue,
        *,
        block: bool = True,
        timeout: float | None = None,
        patience: float = 0.1,
        raise_on_dropped_logs: bool = True,
    ) -> None:
        super().__init__(queue.queue)
        self.context_queue = queue
        self.block = block
        self.timeout = timeout
        self.patience = patience
        self.raise_on_dropped_logs = raise_on_dropped_logs

    @override
    def handleError(self, record: LogRecord) -> None:
        """Custom error handler that optionally raises on dropped logs.

        Args:
            record: The log record that triggered the error.
        """
        if self.raise_on_dropped_logs:
            exc_value = import_lazy("sys").exc_info()[1]
            if isinstance(exc_value, LogRecordDroppedError):
                raise exc_value

        super().handleError(record)

    def _is_listener_alive_and_healthy(self) -> bool:
        """Check whether the listener is alive and healthy.

        Returns:
            True if listener is alive and healthy, False otherwise.
        """
        workers = (
            import_lazy_project(
                "cli.logs.process_logger"
            ).get_all_process_workers()
            | import_lazy_project(
                "cli.logs.thread_logger"
            ).get_all_thread_workers()
        )
        if self.context_queue.name in workers:
            return workers[self.context_queue.name].events.is_healthy()

        return False

    @staticmethod
    def _has_timed_out(deadline: float) -> bool:
        """Determine whether the current time has passed the given deadline.

        Args:
            deadline: The absolute time limit based on a monotonic clock.

        Returns:
            True if the deadline has been reached or passed, False otherwise.
        """
        return import_lazy("time").monotonic() >= deadline

    def _attempt_put(self, record: LogRecord) -> bool:
        """Try to enqueue the given log record with patience-based retry.

        This method attempts to put the log record into the context queue with
        the configured patience duration. If the queue is full, it checks the
        health of the listener. If the listener is unhealthy, it raises
        LogRecordDroppedError.

        Args:
            record: The log record to enqueue.

        Returns:
            True if the record was successfully enqueued, False otherwise.

        Raises:
            LogRecordDroppedError: If the queue is full and the listener is
            determined to be unhealthy.
        """
        try:
            self.context_queue.queue.put(record, self.block, self.patience)
        except Full as full:
            if not self._is_listener_alive_and_healthy():
                raise LogRecordDroppedError(
                    record, "logger is unhealthy"
                ) from full

            return False

        return True

    def _timed_enqueue(self, record: LogRecord) -> None:
        """Attempt to enqueue the record with a retry deadline.

        Repeatedly tries to enqueue the given log record until it succeeds or
        the timeout (based on a monotonic clock) expires. If the queue is full
        and the associated listener appears unhealthy, raises immediately.

        Args:
            record: The log record to enqueue.

        Raises:
            LogRecordDroppedError: If the queue remains full past the timeout
            or if the listener is determined to be unhealthy during retries.
        """
        time = import_lazy("time")
        deadline = time.monotonic() + self.timeout

        while not self._has_timed_out(deadline):
            if self._attempt_put(record):
                return

        raise LogRecordDroppedError(
            record, f"queue is full after {self.timeout}s"
        ) from Full

    def _blocking_enqueue(self, record: LogRecord) -> None:
        """Retry indefinitely until the log record is enqueued.

        Args:
            record: The log record to enqueue.
        """
        while not self._attempt_put(record):
            continue

    @override
    def enqueue(self, record: LogRecord) -> None:
        """Enqueue a log record into the target queue.

        Adds a `record.enqueued_wall_time` timestamp after success.

        Args:
            record: The log record to enqueue.
        """
        time = import_lazy("time")

        if self.timeout is None:
            self._blocking_enqueue(record)
        else:
            self._timed_enqueue(record)

        record.enqueued_wall_time = time.time()
