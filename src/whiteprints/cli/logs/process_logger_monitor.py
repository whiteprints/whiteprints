# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Thread monitoring utilities for logging workers in Whiteprints.

This module implements robust monitoring and shutdown routines for logging
subprocesses launched by the core `process_logger` system. It includes:
  - `monitor_death_process`: A watchdog that observes child listener lifecycles
    and enforces fail-fast shutdowns on silent crashes or drain failures.
  - `shutdown_process`: Cooperative stop-and-wait logic for child logging
    processes.
  - Emergency drain handlers for log records and fatal exceptions.

Design Notes:
  - Emergency draining avoids log loss by re-logging unconsumed records via a
    fallback emergency logger.
  - The monitor thread ensures the parent process cannot continue if a logging
    subprocess exits silently or fails to flush its queue.
  - All operations are hardened with `DelaySignals` to handle fatal signals
    during critical cleanup.
"""

from multiprocessing.context import (
    ForkProcess,
    ForkServerProcess,
    SpawnProcess,
)
from multiprocessing.synchronize import Event as ProcessEvent
from typing import NamedTuple

from whiteprints.concurrency import is_main_process, is_main_thread
from whiteprints.logs.handlers import (
    ContextProcessQueue,
)


__all__ = [
    "Process",
    "ProcessEvents",
    "ProcessWorker",
    "shutdown_process",
]
"""Public module attributes."""

type Process = SpawnProcess | ForkProcess | ForkServerProcess
"""Union of all multiprocessing contexts."""


class ProcessEvents(NamedTuple):
    """Container for synchronization primitives used by a process worker.

    Attributes:
      stop:     Event to request clean shutdown of the listener.
      death:    Event set by the listener on normal or abnormal termination.
    """

    active: ProcessEvent
    healthcheck: ProcessEvent
    stop: ProcessEvent
    death: ProcessEvent

    def is_healthy(self) -> bool:
        """Check if the process is healthy.

        Returns:
            True if the process is in a healthy active state.
        """
        return (
            self.active.is_set()
            and self.healthcheck.is_set()
            and not self.stop.is_set()
            and not self.death.is_set()
        )

    def __repr__(self) -> str:
        """Return a compact string summary of event states.

        Shows each event (active, stop, death) as either 'set'
        or 'unset', avoiding internal memory addresses or object ids.

        Returns:
            A string representation such as:
            'ProcessEvents(active=set, stop=unset, death=set)'
        """

        def status(event: ProcessEvent) -> str:
            return "set" if event.is_set() else "unset"

        return (
            f"{self.__class__.__name__}("
            f"active={status(self.active)}, "
            f"stop={status(self.stop)}, "
            f"death={status(self.death)}, "
        )


class ProcessWorker(NamedTuple):
    """Metadata associated with a spawned logging process.

    Tracks the subprocess, its synchronization events, and its communication
    channels for error reporting and record draining.

    Attributes:
      worker: The `multiprocessing.Process` that runs the logging listener.
      parent_pid: PID of the process that spawned this worker.
      events: A `ProcessEvents` object with shutdown and death signals.
      exception: Queue used to report setup or runtime failures to parent.
      drain: Queue used to send unconsumed log records on shutdown.
    """

    worker: Process
    parent_pid: int
    events: ProcessEvents
    records: ContextProcessQueue


def shutdown_process(process_worker: ProcessWorker) -> None:
    """Request a logging subprocess to exit and wait for termination.

    If called from the parent process that spawned the worker, this sets the
    stop event and polls the process for termination within the given patience
    window. If called from a child process, it returns immediately.

    Args:
        process_worker: The process worker to shut down.
        patience: Total maximum duration to wait (in seconds).
        timeout: Sleep/poll interval between join attempts.
    """
    print("SHUTDOWN LOGGER")
    if is_main_thread() and is_main_process():
        print("STARTING SHUTDOWN LOGGER EVENT")
        process_worker.records.queue.put(None)
        print("STARTING SHUTDOWN LOGGER JOIN")
        process_worker.worker.join()
        print("STARTING SHUTDOWN LOGGER CLOSE")
        process_worker.worker.close()
        print("STARTING SHUTDOWN LOGGER END")
