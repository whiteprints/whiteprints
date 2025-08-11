# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Supervisor module for structured logging worker orchestration.

This module ensures that all registered logging queues — both thread-based and
process-based — have active listeners. It acts as a coordinator: spawning the
appropriate type of listener for each queue, applying daemonization policies,
and avoiding redundant activation of already-running workers.

Note:
This module no longer handles low-level process monitoring or emergency
shutdown. That logic is now delegated to `process_logger_monitor`, which
manages draining and forced termination on child failure.

Responsibilities:
  - Spawn subprocesses (`multiprocessing.Process`) for all known
    `worker_spawn_<label>` queues via `spawn_logging_process`.
  - Spawn background threads (`threading.Thread`) for all
    `worker_thread_<label>` queues via `spawn_logging_thread`.
  - Enforce one active listener per queue — no duplication or collision.
  - Apply daemonization policy (`Daemon`) to each worker and its monitor
    thread.

Guarantees:
  - Each logging queue from the configuration layer will be served by one
    and only one active listener.
  - Spawning is idempotent and repeat-safe (no double instantiation).
  - External systems can call `spawn()` to fully initialize logging execution.
"""

from whiteprints.lazy_import import import_lazy_project
from whiteprints.logs.logs_interface import Daemon


__all__ = ["spawn"]
"""Public module attributes."""


def _spawn_all_process_loggers(daemon: Daemon) -> None:
    """Start all uninitialized process-based logging listeners.

    Iterates over all registered `ContextProcessQueue` instances and spawns
    a subprocess per queue not already managed. Each process consumes log
    records from its queue and emits them to non-QueueHandler sinks.

    Args:
        patience: Grace time (in seconds) to allow for shutdown.
        timeout: Polling interval during shutdown join cycles.
        daemon: Daemon mode control for each listener and its monitor thread.

    Notes:
        Idempotent — skips queues already associated with active workers.
        This function does not install signal handlers; it is designed for
        internal orchestration by a higher-level controller.
    """
    process_logger = import_lazy_project("cli.logs.process_logger")
    known = process_logger.get_all_process_workers()

    for name, context_queue in (
        import_lazy_project("logs.logs_queue").get_all_process_queues().items()
    ):
        if name in known:
            continue

        process_logger.spawn_logging_process(context_queue, daemon)


def _spawn_all_thread_loggers(daemon: Daemon) -> None:
    """Start all uninitialized thread-based logging listeners.

    Iterates over all registered `ContextThreadQueue` instances and spawns
    a thread per queue not already managed. Each thread consumes log
    records and emits them to non-QueueHandler sinks.

    Args:
        patience: Grace time (in seconds) to allow for shutdown.
        timeout: Polling interval during shutdown join cycles.
        daemon: Daemon mode control for each listener and its monitor thread.

    Notes:
        Idempotent — skips queues already bound to live listeners.
        No signal handlers are installed at this level.
    """
    thread_logger = import_lazy_project("cli.logs.thread_logger")
    queue = import_lazy_project("logs.logs_queue")
    known = thread_logger.get_all_thread_workers()

    for name, context_queue in queue.get_all_thread_queues().items():
        if name in known:
            continue

        thread_logger.spawn_logging_thread(context_queue, daemon)


def spawn(
    *,
    daemon_worker: bool = False,
    daemon_monitor: bool = False,
) -> None:
    """Launch all missing logging listeners (processes and threads).

    Coordinates full setup across all registered logging queues. Ensures
    exactly one listener per queue, and registers exit signal handlers
    (SIGINT, SIGTERM) for deterministic shutdown via stop events and joins.

    Args:
        patience: Max time (in seconds) to wait for clean shutdown.
        timeout: Polling interval during shutdown joins.
        daemon_worker: Whether logging workers (thread or process) should
            run in daemon mode. See `Daemon` for implications.
        daemon_monitor: Whether monitor threads should be daemons.

    Notes:
        Unless the execution environment prevents reliable `atexit`/signal
        handling, keep both daemon flags set to False. This system is
        engineered to support robust, cooperative shutdown under normal
        and abnormal termination paths.
    """
    daemon = import_lazy_project("logs.logs_interface").Daemon(
        worker=daemon_worker,
        monitor=daemon_monitor,
    )
    _spawn_all_process_loggers(daemon)
    _spawn_all_thread_loggers(daemon)
