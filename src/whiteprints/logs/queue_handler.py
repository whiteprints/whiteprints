# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging handlers."""

import atexit
import importlib
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

        It inherits from logging.QueueListener and start/stop the queue
        automatically on instanciation and destruction.

        Example:
            >>> from queue import Queue
            >>>
            >>> AutoStartQueueListener(Queue())
            < ... AutoStartQueueListener ... >

        Args:
            queue: a log events queue
            handlers: the handlers pushing to the queue
            respect_handler_level: respect the handlers logging levels
        """
        super().__init__(
            queue, *handlers, respect_handler_level=respect_handler_level
        )
        self.start()
        atexit.register(self.stop)

    def stop(self) -> None:
        """Stop the queue.

        Example:
            >>> from queue import Queue
            >>>
            >>> handler = AutoStartQueueListener(
            >>>     Queue()
            >>> )
            >>> handler.stop()
            None
        """
        # required when not sys.version_info >= (3, 13)
        # thread stopping may be called more than once.
        # see CPython issue gh-114706
        with importlib.import_module("contextlib").suppress(AttributeError):
            self.stop()
