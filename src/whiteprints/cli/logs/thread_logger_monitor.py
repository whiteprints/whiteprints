# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread monitoring utilities for logging workers in Whiteprints.

This module implements robust monitoring and shutdown routines for structured
logging threads launched by the core `thread_logger` system. It includes:
  - `monitor_death_thread`: A watchdog that observes background listener
    threads
    and enforces emergency drain and cleanup on silent crashes or drain
    failures.
  - `shutdown_thread`: Cooperative stop-and-wait logic for thread-based
    loggers.
  - Emergency drain handlers for log records and fatal exceptions.

Design Notes:
  - Emergency draining avoids log loss by re-logging unconsumed records using
    the fallback emergency logger.
  - The monitor thread ensures failures in thread-based logging listeners are
    detected early and do not silently compromise observability.
  - All operations are guarded with `DelaySignals` to handle interruptions
    safely during critical log draining and teardown.
"""

from logging import LogRecord
from queue import Queue as ThreadQueue
from threading import Event as ThreadEvent
from threading import Thread
from typing import NamedTuple

from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.signals_handler import DelaySignals


__all__ = [
    "DrainQueues",
    "Thread",
    "ThreadEvents",
    "ThreadWorker",
    "monitor_death_thread",
    "shutdown_thread",
]
"""Public module attributes."""


class ThreadEvents(NamedTuple):
    """Container for synchronization primitives used by a thread worker.

    Attributes:
        active: Event set when the listener thread is running.
        stop: Event used to request clean shutdown of the listener.
        death: Event set when the listener exits, whether normally or
            abnormally.
        drained: Event set when all log records have been flushed or drained.
    """

    active: ThreadEvent
    healthcheck: ThreadEvent
    stop: ThreadEvent
    death: ThreadEvent
    drained: ThreadEvent

    def is_healthy(self) -> bool:
        """Check if the thread is healthy.

        Returns:
            True if the thread is in a healthy active state.
        """
        return (
            self.active.is_set()
            and self.healthcheck.is_set()
            and not self.stop.is_set()
            and not self.death.is_set()
            and not self.drained.is_set()
        )

    def __repr__(self) -> str:
        """Return a compact string summary of event states.

        Shows each event (active, stop, death, drained) as either 'set'
        or 'unset', avoiding internal memory addresses or object ids.

        Returns:
            A string representation such as:
            'ThreadEvents(active=set, stop=unset, death=set, drained=unset)'
        """

        def status(event: ThreadEvent) -> str:
            return "set" if event.is_set() else "unset"

        return (
            f"{self.__class__.__name__}("
            f"active={status(self.active)}, "
            f"stop={status(self.stop)}, "
            f"death={status(self.death)}, "
            f"drained={status(self.drained)})"
        )


class ThreadWorker(NamedTuple):
    """Metadata associated with a spawned logging thread.

    Tracks the subthread, its synchronization events, and its communication
    channels for error reporting and record draining.

    Attributes:
        worker: The `threading.Thread` that runs the logging listener.
        parent_pid: The process ID of the thread's creator (same across
            threads).
        events: A `ThreadEvents` object with shutdown and death signals.
        exception: Queue used to report setup or runtime failures to the
            parent.
        drain: Queue used to send unconsumed log records at shutdown.
    """

    worker: Thread
    parent_pid: int
    events: ThreadEvents
    exception: ThreadQueue[BaseException]
    drain: ThreadQueue[LogRecord]


class DrainQueues(NamedTuple):
    """Group of queues used for emergency log draining.

    Attributes:
        exceptions: Queue used for fatal listener errors.
        records: Queue used for unconsumed `LogRecord`s at shutdown.
    """

    exceptions: ThreadQueue[BaseException]
    records: ThreadQueue[LogRecord]


def shutdown_thread(
    thread_worker: ThreadWorker, patience: float, timeout: float
) -> None:
    """Request a logging subthread to exit and wait for termination.

    If called from the parent thread that spawned the worker, this sets the
    stop event and polls the thread for termination within the given patience
    window. If called from a child thread, it returns immediately.

    Args:
        thread_worker: The thread worker to shut down.
        patience: Total maximum duration to wait (in seconds).
        timeout: Sleep/poll interval between join attempts.
    """
    time = import_lazy("time")

    thread_worker.events.stop.set()

    deadline = time.time() + patience
    worker = thread_worker.worker

    while worker.is_alive() and time.time() < deadline:
        worker.join(timeout)


def _drain_exception_queue(queue: ThreadQueue[BaseException]) -> None:
    """Flush exceptions from a failed listener thread to the emergency logger.

    This function resets the logging system and logs each fatal exception
    with CRITICAL severity. It is only invoked after the death event is set.

    Args:
        queue: Exception queue from the failed listener thread.
    """
    if queue.empty():
        return

    logger = import_lazy_project("cli.logs").LOGGING.get_logger()

    with DelaySignals():
        while not queue.empty():
            logger.critical(queue.get_nowait())

    import_lazy_project("logs.logs_queue").terminate_thread_queue(queue)


def _drain_record_queue(queue: ThreadQueue[LogRecord]) -> None:
    """Flush unconsumed log records to the emergency logger.

    Used when a listener thread shuts down before processing all log records.
    Each message is logged with CRITICAL severity to prevent silent loss.

    Args:
        queue: Queue containing leftover `LogRecord`s.
    """
    if queue.empty():
        return

    logger = import_lazy_project("cli.logs").LOGGING.get_logger()

    with DelaySignals():
        while not queue.empty():
            logger.critical(queue.get_nowait())

    import_lazy_project("logs.logs_queue").terminate_thread_queue(queue)


def monitor_death_thread(
    drain_queues: DrainQueues,
    worker: ThreadWorker,
    patience: float,
    timeout: float,
    idle_time: float = 0.1,
    max_unhealthy_cycles: int = 100,
) -> None:
    """Background thread to monitor abnormal listener thread termination.

    Waits for the `drained` event, flushes both the `exception_queue` and
    `drain_queue` to the emergency logger, and initiates shutdown.

    This provides fail-fast behavior when logging threads crash silently
    or fail to consume all log records.

    Args:
        drain_queues: Queues to flush on listener failure.
        worker: The `ThreadWorker` instance managing the listener thread.
        patience: Maximum time to wait for clean shutdown (in seconds).
        timeout: Poll interval between join attempts (in seconds).
        idle_time: Sleep interval for polling the drained flag (in seconds).
    """
    unhealthy_cycles = 0
    while not worker.events.drained.is_set():
        if not worker.events.is_healthy():
            unhealthy_cycles += 1
        else:
            unhealthy_cycles = 0

        worker.events.healthcheck.clear()

        if unhealthy_cycles >= max_unhealthy_cycles:
            break

        worker.events.drained.wait(idle_time)

    import_lazy_project("cli.logs").LOGGING.emergency_configuration_reset(
        import_lazy_project("cli").ENV
    )

    if not worker.events.drained.is_set():
        logger = import_lazy_project("cli.logs").LOGGING.get_logger()
        logger.critical(
            _(
                "Logging thread marked unhealthy "
                "— terminating after %s failed health checks"
            ),
            max_unhealthy_cycles,
            extra={
                "thread_name": worker.worker.name,
                "thread_id": worker.worker.ident,
                "parent_pid": worker.worker.native_id,
            },
        )
        os = import_lazy("os")
        os.kill(worker.parent_pid, import_lazy("signal").SIGTERM)
    else:
        _drain_exception_queue(drain_queues.exceptions)
        _drain_record_queue(drain_queues.records)
        shutdown_thread(worker, patience, timeout)
