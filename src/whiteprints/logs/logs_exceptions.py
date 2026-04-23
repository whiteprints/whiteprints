# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging exception."""

from logging import LogRecord
from typing import Final, TypedDict

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _


__all__: Final = [
    "InvalidRedactionModeError",
    "InvalidStacktraceModeError",
    "InvalidTracebackModeError",
    "LogTraceConfig",
]
"""Public module attributes."""


TRACEBACK_MODES: Final = ["clear", "suppress", "hash"]
"""Available traceback redaction mode"""
STACKTRACE_MODES: Final = ["clear", "suppress", "hash", "path_redact"]
"""Available stactrace redaction mode"""


class InvalidRedactionModeError(WhiteprintsError):
    """Raised when a redaction mode string is invalid."""


class LogRecordDroppedError(WhiteprintsError):
    """Raised when a log record is dropped."""

    def __init__(self, record: LogRecord, reason: str | None = None) -> None:
        """Initialize the error with the dropped LogRecord.

        Args:
            record: The LogRecord that could not be enqueued.
            reason: Optional explanation (e.g., 'listener is dead',
                'queue full').
        """
        self.record = record
        self.reason = reason or _("log record could not be enqueued.")
        msg = _("Dropped log record — reason: {}").format(self.reason)
        super().__init__(msg)


class InvalidTracebackModeError(InvalidRedactionModeError):
    """Raised when an invalid traceback redaction mode is configured."""

    def __init__(self, mode: str) -> None:
        """Initialize the error with the invalid mode string.

        Args:
            mode: The invalid redaction mode that triggered the exception.
        """
        super().__init__(
            _("Invalid 'traceback_mode': '{}', possible modes are {}").format(
                mode,
                TRACEBACK_MODES,
            )
        )
        self.mode = mode


class InvalidStacktraceModeError(InvalidRedactionModeError):
    """Raised when an invalid stacktrace redaction mode is configured."""

    def __init__(self, mode: str) -> None:
        """Initialize the traceback mode error.

        Args:
            mode: The invalid traceback mode passed to the filter.
        """
        super().__init__(
            _("Invalid 'stacktrace_mode': '{}', possible modes are {}").format(
                mode,
                STACKTRACE_MODES,
            )
        )
        self.mode = mode


class LogTraceConfig(TypedDict):
    """Holds `stack_info` and `exc_info` values for logging tracebacks."""

    stack_info: bool
    exc_info: BaseException | None
