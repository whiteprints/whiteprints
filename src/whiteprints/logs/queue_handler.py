# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging handlers."""

import sys
from logging import Handler, LogRecord
from logging.handlers import QueueListener
from queue import Queue
from typing import Final


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["AutoStartQueueListener"]


class AutoStartQueueListener(QueueListener):
    """A `logging.QueueListener` that autostarts."""

    @override
    def __init__(
        self,
        queue: Queue[LogRecord],
        *handlers: Handler,
        respect_handler_level: bool = False,
    ) -> None:
        """Initialise the instance.

        Use the specified queue and handlers.

        Args:
            queue: a log events queue
            handlers: the handlers pushing to the queue
            respect_handler_level: respect the handlers logging levels
        """
        super().__init__(
            queue, *handlers, respect_handler_level=respect_handler_level
        )
        self.start()

    def __del__(self) -> None:
        """Stop the queue."""
        self.stop()
