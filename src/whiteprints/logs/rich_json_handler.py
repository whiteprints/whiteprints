# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging handlers."""

import importlib
import sys
from collections.abc import Mapping
from logging import Handler, LogRecord
from typing import (
    Any,
    Final,
    Optional,
)


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["RichJSONHandler"]


class RichJSONHandler(Handler):
    """Rich logging Handler."""

    @override
    def __init__(
        self,
        console_args: Optional[Mapping[str, Any]] = None,
        print_json_args: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Initialize the logging Handler.

        Args:
            console_args: arguments forwarded to the `rich.console.Console`
                instance
            print_json_args: arguments forwarded to the `print_json` method of
                the rich Console.
        """
        super().__init__()
        self.console = importlib.import_module("rich.console").Console(
            **(console_args or {"stderr": True})
        )
        self.print_json_args = print_json_args or {"indent": None}
        self.error = importlib.import_module("rich.errors")
        self.NullFile = importlib.import_module("rich.logging").NullFile

    @override
    def emit(self, record: LogRecord) -> None:
        """Emit a record.

        If a formatter is specified, it is used to format the record.

        Args:
            record: the record use to emit the log.
        """
        message = self.format(record)

        if isinstance(self.console.file, self.NullFile):
            self.handleError(record)
        else:
            try:
                self.console.print_json(message, **self.print_json_args)
            except (self.error.ConsoleError, self.error.StyleError):
                self.handleError(record)
