# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Queue-specific exceptions.

This module defines the error hierarchy for queue operations, covering
ownership violations, shutdown access, capacity limits, and task tracking
errors. All exceptions inherit from QueueError and apply uniformly across
thread- and process-based queue backends.
"""

from typing import Final

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _


__all__: Final = [
    "EmptyError",
    "FullError",
    "NotOwningError",
    "QueueError",
    "ShutDownError",
    "TaskDoneOverflowError",
]
"""Public module attributes."""


class QueueError(WhiteprintsError):
    """Base class for all queue-related exceptions.

    This exception serves as the root for all errors raised by the queue
    system. Use it to catch all queue-specific issues generically.
    """


class NotOwningError(QueueError):
    """raised when shutdown is attempted by a non-owning worker.

    Ownership is a local property associated with either a thread or a
    process, depending on the queue backend. Only the owning context is
    allowed to manage the queue lifecycle.

    This error is raised if a shutdown is attempted from a context that
    does not own the queue. Worker threads or processes must not call
    `shutdown()`, `close()`, or trigger shutdown via `__exit__()`.

    Use this to enforce safe termination rules in concurrent programs
    across threads or processes.

    Backends should define what constitutes an owning context and raise
    this error accordingly.
    """


class ShutDownError(QueueError):
    """Raised when the queue is accessed after shutdown.

    This occurs if an operation like `put()` or `get()` is attempted after
    the queue has been shut down, either explicitly or via a sentinel.
    """


class FullError(QueueError):
    """Raised when trying to put into a full queue without blocking.

    Also raised if the put operation times out before space becomes
    available.
    """


class EmptyError(QueueError):
    """Raised when trying to get from an empty queue without blocking.

    Also raised if the get operation times out before an item is available.
    """


class TaskDoneOverflowError(QueueError):
    """Raised when task_done() is called too many times.

    This indicates more calls to task_done() than items were added to the
    queue, breaking task tracking for join().
    """
