# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging formatters."""

import json
import sys
from logging import Formatter, LogRecord
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    Final,
)


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["JSONFormatter"]


class JSONFormatter(Formatter):
    """A JSON log formatter for structured logs."""

    _DUMMY_RECORD_KEYS: ClassVar = LogRecord(
        "dummy",
        0,
        "dummy",
        0,
        None,
        None,
        None,
    ).__dict__.keys()
    """A dummy record use to extract the extra keys from a record"""

    @classmethod
    def _extract_extras(cls, record: LogRecord) -> dict[str, Any]:
        """Extract the extra keys from a record.

        If the extra key is a callable that takes no ars, it will be called.
        This allow defered evaluation of the extras at logging time.

        Args:
            record: a record containing some extra keys.

        Returns:
            The extra keys.
        """
        return {
            key: value() if callable(value) else value
            for key, value in record.__dict__.items()
            if key not in cls._DUMMY_RECORD_KEYS
        }

    @override
    def format(self, record: LogRecord) -> str:
        """Format a record.

        Args:
            record: the record to format.

        Returns:
            a JSON string representing the record.
        """
        struct_log = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": {
                "name": record.levelname,
                "value": int(record.levelno),
            },
            "context": {
                "logger_name": record.name,
                "dynamic": {
                    "relative_time": record.relativeCreated,
                    "process": {
                        "name": record.processName,
                        "id": record.process,
                    },
                    "thread": {
                        "name": record.threadName,
                        "id": record.thread,
                    },
                    "task": {
                        "name": getattr(record, "taskName", None),
                    },
                },
                "static": {
                    "logical": {
                        "function": record.funcName,
                    },
                    "physical": {
                        "path": str(Path(record.pathname)),
                        "line": record.lineno,
                    },
                },
                "exception": {
                    "traceback": (
                        self.formatException(record.exc_info)
                        if record.exc_info
                        else None
                    ),
                    "stack": (
                        self.formatStack(record.stack_info)
                        if record.stack_info
                        else None
                    ),
                    "text": record.exc_text,
                },
            },
            "extra": self._extract_extras(record),
            "message": record.getMessage(),
        }
        return json.dumps(struct_log)
