# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging filters for the Whiteprints library.

This module defines reusable logging filters for sanitizing sensitive
information in log records. Filters here can be extended or added to provide
additional redaction or transformation logic.
"""

from collections.abc import Iterable
from functools import cached_property
from logging import Filter, LogRecord
from types import TracebackType
from typing import Final, Literal, override

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.logs.logs_exceptions import (
    InvalidStacktraceModeError,
    InvalidTracebackModeError,
)
from whiteprints.redaction import SafeString
from whiteprints.redactor import PathRedactor


__all__: Final = [
    "AttributeValueFilter",
    "ContextualFilter",
    "DebugOnlyFilter",
    "LevelRangeFilter",
    "MessageRegexFilter",
    "RedactedTracebackAndStackTraceFilter",
    "SuppressLoggerNameFilter",
    "SuppressLoggerNameRegexFilter",
]
"""Public module attributes."""


class RedactedTracebackAndStackTraceFilter(Filter):
    """Redaction of Tracebacks and Stack traces.

    Intercepts exception information (`exc_info`) and stack
    snapshots (`stack_info`), replaces the raw details with concise hashes, and
    attaches a structured `exception` attribute containing:
      - exception_type: Name of the exception class
      - exception_message: Stringified exception message
      - crash_id: Short hash of the full traceback, or None if unavailable
      - stack_id: Short hash of the raw stack info, if provided

    After redaction, the original `exc_info`, `exc_text`, and `stack_info`
    fields are cleared to prevent leakage of file paths or other sensitive
    details.
    """

    __slots__ = ("stacktrace_mode", "traceback_mode")

    def __init__(
        self,
        name: str = "",
        traceback_mode: Literal["clear", "suppress", "hash"] = "hash",
        stacktrace_mode: Literal[
            "clear", "suppress", "hash", "path_redact"
        ] = "path_redact",
    ) -> None:
        """Initialize the filter with specified modes.

        Args:
            name: Optional filter name.
            traceback_mode: One of 'clear', 'suppress', or 'hash'.
            stacktrace_mode: One of 'clear', 'suppress', 'hash', or
                'path_redacted'.

        Raises:
            InvalidTracebackModeError: If traceback_mode is invalid.
            InvalidStacktraceModeError: If stacktrace_mode is invalid.
        """
        if (
            traceback_mode
            not in import_lazy_project("logs.logs_exceptions").TRACEBACK_MODES
        ):
            raise InvalidTracebackModeError(traceback_mode)

        if (
            stacktrace_mode
            not in import_lazy_project("logs.logs_exceptions").STACKTRACE_MODES
        ):
            raise InvalidStacktraceModeError(stacktrace_mode)

        super().__init__(name)
        self.traceback_mode = traceback_mode
        self.stacktrace_mode = stacktrace_mode

    @cached_property
    def _path_redactor(self) -> PathRedactor:
        """Lazily import and return the PathRedactor instance."""
        return import_lazy_project("redactor").PathRedactor()

    @staticmethod
    def _hash_traceback(
        record: LogRecord,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        redacted: dict[
            str, list[str] | list[SafeString] | SafeString | str | None
        ],
    ) -> None:
        """Generate a SHA256 hash of the formatted traceback.

        Clears record.exc_info and record.exc_text after hashing.

        Args:
            record: The LogRecord containing exception info.
            exc_type: The exception class type.
            exc_val: The exception instance.
            exc_tb: The traceback object associated with the exception.
            redacted: A dict to populate with redacted exception data.
        """
        crash_id = None
        traceback = import_lazy("traceback")
        if exc_type and exc_val and exc_tb:
            hashlib = import_lazy("hashlib")

            tb_text = "".join(
                traceback.format_exception(exc_type, exc_val, exc_tb)
            )
            crash_id = hashlib.sha256(tb_text.encode()).hexdigest()

        redacted["exception_type"] = exc_type.__name__ if exc_type else None
        lines = traceback.format_exception_only(exc_type, exc_val)
        redacted["exception_message"] = lines[-1].strip() if lines else ""
        redacted["crash_id"] = f"sha256={crash_id}"

        record.exc_info = None
        record.exc_text = None

    def _redact_traceback(
        self,
        record: LogRecord,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
        redacted: dict[
            str, list[str] | list[SafeString] | SafeString | str | None
        ],
    ) -> None:
        """Apply the configured traceback redaction policy to the record.

        Args:
            record: The LogRecord to modify.
            exc_type: The exception class type.
            exc_val: The exception instance.
            exc_tb: The traceback object.
            redacted: A dict to store redacted exception data.
        """
        match self.traceback_mode:
            case "clear":
                return
            case "hash":
                self._hash_traceback(
                    record, exc_type, exc_val, exc_tb, redacted
                )
            case _:
                record.exc_info = None
                record.exc_text = None

    def _redact_stacktrace(
        self,
        record: LogRecord,
        stack_info: str,
        redacted: dict[
            str, list[str] | list[SafeString] | SafeString | str | None
        ],
    ) -> None:
        """Apply the configured stacktrace redaction policy to the record.

        Args:
            record: The LogRecord containing stack info.
            stack_info: The raw stack_info string.
            redacted: A dict to store redacted stack data.
        """
        match self.stacktrace_mode:
            case "clear":
                return
            case "path_redact":
                redaction = import_lazy_project("redaction")
                redacted["stack"] = [
                    redaction.Sensitive(
                        line,
                        self._path_redactor,
                        "record.stack_info",
                    )
                    for line in stack_info.splitlines()
                ]
                record.stack_info = None
            case "hash":
                hashlib = import_lazy("hashlib")
                stack_id = hashlib.sha256(stack_info.encode()).hexdigest()
                redacted["stack_id"] = f"sha256={stack_id}"
                record.stack_info = None
            case _:
                record.stack_info = None

    @override
    def filter(self, record: LogRecord) -> Literal[True]:
        """Redact exception and stack trace data from the given LogRecord.

        Args:
            record: The LogRecord to process.

        Returns:
            True (to ensure the record is always emitted).
        """
        redacted: dict[
            str, list[SafeString] | list[str] | str | SafeString | None
        ] = {}

        if record.exc_info and any(record.exc_info):
            exc_type, exc_val, exc_tb = record.exc_info
            self._redact_traceback(
                record,
                exc_type,
                exc_val,
                exc_tb,
                redacted,
            )

        if record.stack_info:
            self._redact_stacktrace(record, record.stack_info, redacted)

        if redacted:
            record.exception = redacted

        return True


class SuppressLoggerNameRegexFilter(Filter):
    """Filter that suppresses logs whose logger name matches a given regex."""

    __slots__ = ("_pattern",)

    def __init__(self, pattern: str) -> None:
        """Initialize the filter with a regex pattern.

        Args:
            pattern: Regular expression string to match against logger names.
        """
        super().__init__()
        self._pattern = import_lazy("re").compile(pattern)

    @override
    def filter(self, record: LogRecord) -> bool:
        """Determine if the specified record is to be logged.

        Returns False if the logger name matches the regex pattern.

        Args:
            record: The LogRecord to test.

        Returns:
            True if the record should be logged, False if it should be
            suppressed.
        """
        return not self._pattern.search(record.name)


class SuppressLoggerNameFilter(Filter):
    """Suppresses logs with logger names starting with some prefix."""

    __slots__ = ("_prefixes",)

    def __init__(self, prefixes: Iterable[str]) -> None:
        """Initialize the filter with one or more logger name prefixes.

        Args:
            prefixes: Logger name prefixes to block (e.g.,
            ['whiteprints.debug']).
        """
        super().__init__()
        self._prefixes = frozenset(prefixes)

    @override
    def filter(self, record: LogRecord) -> bool:
        """Filter record.

        Suppress record if its logger name starts with any of the defined
        prefixes.

        Args:
            record: The LogRecord to evaluate.

        Returns:
            False if suppressed, True otherwise.
        """
        return not any(record.name.startswith(p) for p in self._prefixes)


class LevelRangeFilter(Filter):
    """Filters log records by enforcing a minimum and maximum log level."""

    def __init__(
        self,
        name: str = "",
        min_level: int = 10,
        max_level: int = 50,
    ) -> None:
        """Initialize LevelRangeFilter with optional level bounds.

        Args:
            name: Optional filter name.
            min_level: Minimum log level (inclusive) to allow.
            max_level: Maximum log level (inclusive) to allow.
        """
        super().__init__(name)
        self.min_level = min_level
        self.max_level = max_level

    @override
    def filter(self, record: LogRecord) -> bool:
        return self.min_level <= record.levelno <= self.max_level


class DebugOnlyFilter(Filter):
    """Filters log records based on a debug mode flag."""

    def __init__(self, name: str = "", *, debug: bool = True) -> None:
        """Initialize DebugOnlyFilter.

        Args:
            name: Optional filter name.
            debug: When True, allows all records; otherwise, suppresses all.
        """
        super().__init__(name)
        self.debug = debug

    @override
    def filter(self, record: LogRecord) -> bool:
        return self.debug


class ContextualFilter(Filter):
    """Injects contextual information into log records."""

    def __init__(
        self,
        name: str = "",
        context: dict[str, object] | None = None,
    ) -> None:
        """Initialize ContextualFilter.

        Args:
            name: Optional filter name.
            context: Dictionary of key-value pairs to add to each log record.
        """
        super().__init__(name)
        self.context = context or {}

    @override
    def filter(self, record: LogRecord) -> bool:
        for k, v in self.context.items():
            setattr(record, k, v)
        return True


class AttributeValueFilter(Filter):
    """Filters log records based on a specific attribute's value."""

    def __init__(
        self,
        name: str = "",
        attr: str | None = None,
        value: object = None,
    ) -> None:
        """Initialize AttributeValueFilter.

        Args:
            name: Optional filter name.
            attr: Attribute name to check on the log record.
            value: Expected value of the attribute to allow the record.
        """
        super().__init__(name)
        self.attr = attr
        self.value = value

    @override
    def filter(self, record: LogRecord) -> bool:
        if self.attr is None:
            return True

        return getattr(record, self.attr, None) == self.value


class MessageRegexFilter(Filter):
    """Filter log records by matching their message against a regex."""

    def __init__(
        self,
        name: str = "",
        pattern: str = r"*",
        *,
        exclude: bool = False,
    ) -> None:
        """Initialize MessageRegexFilter.

        Args:
            name: Optional filter name.
            pattern: Regex pattern to match against the log message.
            exclude: If True, exclude matching messages; if False, include only
                matching messages.
        """
        super().__init__(name)
        self.pattern = import_lazy("re").compile(pattern)
        self.exclude = exclude

    @override
    def filter(self, record: LogRecord) -> bool:
        message = record.getMessage()
        match = bool(self.pattern.search(message))
        return not match if self.exclude else match
