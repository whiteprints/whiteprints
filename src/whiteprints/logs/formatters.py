# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging formatters."""

from collections.abc import Mapping
from datetime import tzinfo
from logging import Formatter, LogRecord
from typing import (
    Any,
    ClassVar,
    Final,
    Literal,
    TypedDict,
    override,
)

from whiteprints.concurrency import session_id
from whiteprints.lazy_import import (
    import_extra,
    import_lazy,
    import_lazy_project,
)
from whiteprints.package_constants import is_true


__all__: Final = ["StructFormatter"]
"""Public module attributes."""


class _TraceBackJSON(TypedDict):
    """JSONserializable representation of an exception trace."""

    exception_type: str | None
    exception_message: str
    traceback: list[list[str]]


def _logrecord_exception_to_dict(
    record: LogRecord,
) -> _TraceBackJSON | None:
    """Convert a LogRecord exception into a _TraceBackJSON.

    Returns:
        A _TraceBackJSON representing the exception in the record.
    """
    if record.exc_info is None:
        return None

    return {
        "exception_type": (
            None if record.exc_info[0] is None else record.exc_info[0].__name__
        ),
        "exception_message": str(record.exc_info[1]),
        "traceback": [
            frame.splitlines()
            for frame in import_lazy("traceback").format_tb(
                record.exc_info[2], limit=None
            )
        ],
    }


class StructFormatter(Formatter):
    """A JSON log formatter for structured logs."""

    _DUMMY_RECORD_KEYS: ClassVar = LogRecord(
        "_dummy",
        0,
        "_dummy",
        0,
        "_dummy",
        (),
        None,
    ).__dict__.keys()
    """A dummy record use to extract the extra keys from a record"""

    @override
    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        style: Literal["%", "{"] = "%",
        validate: bool = True,
        *,
        compact_extras: bool = True,
        human_extra: bool = True,
        human_extra_message_sep: str = "\n> ",
        splitlines_message: bool = True,
        defaults: Mapping[str, Any] | None = None,
        structured: str | bool = False,
        json_indent: int | None = None,
        rich_pprint: bool = False,
    ) -> None:
        super().__init__(
            fmt=fmt,
            datefmt=datefmt,
            style=style,
            validate=validate,
            defaults=defaults,
        )
        self.structured = structured
        self.json_indent = json_indent
        self.human_extra = human_extra
        self.human_extra_message_sep = human_extra_message_sep
        self.splitlines_message = splitlines_message
        self.compact_extras = compact_extras
        self.redaction = import_lazy_project("redaction")
        self.path_redactor = import_lazy_project("redactor").PathRedactor()

        self.pprint = (
            pretty.pretty_repr
            if (
                (pretty := import_extra("rich.pretty")) is not None
                and rich_pprint
            )
            else None
        )

    @classmethod
    def _extract_extras(cls, record: LogRecord) -> dict[str, Any]:
        """Extract the extra keys from a record.

        If the extra key is a callable that takes no args, it will be called.
        This allow defered evaluation of the extras at logging time.

        Args:
            record: a record containing some extra keys.

        Returns:
            The extra keys.
        """
        return {
            key: (value() if callable(value) else value)
            for key, value in record.__dict__.items()
            if key not in cls._DUMMY_RECORD_KEYS
            and key
            not in {
                "message",
                "queue_size",
                "emitted_wall_time",
                "dequeued_wall_time",
                "enqueued_wall_time",
                "processed_wall_time",
            }
        }

    @override
    def formatTime(
        self,
        record: LogRecord,
        datefmt: str | None = None,
        tz: tzinfo | None = None,
    ) -> str:
        date_time = import_lazy("datetime").datetime.fromtimestamp(
            record.created, tz=tz
        )
        if datefmt:
            return date_time.strftime(datefmt)

        return date_time.isoformat()

    def _format_structured(
        self, record: LogRecord, extras: dict[str, Any]
    ) -> str:
        """Format a LogRecord into structured JSON format.

        Args:
            record: The log record to format.
            extras: A dictionary of extra fields extracted from the record.

        Returns:
            A JSON-encoded string representing the structured log entry.
        """
        message = record.getMessage()
        struct_log: dict[str, Any] = {
            "timestamp": self.formatTime(
                record,
                self.datefmt,
                import_lazy("datetime").timezone.utc,
            ),
            "severity": {
                "name": record.levelname,
                "value": int(record.levelno),
            },
            "context": {
                "session_id": session_id(),
                "logger_name": record.name,
                "dynamic": {
                    "statistics": {
                        "relative_created": record.relativeCreated,
                        "emitted_wall_time": getattr(
                            record, "emitted_wall_time", None
                        ),
                        "processed_wall_time": None,
                        "queue": {
                            "size": getattr(record, "queue_size", None),
                            "enqueued_wall_time": getattr(
                                record,
                                "enqueued_wall_time",
                                None,
                            ),
                            "dequeued_wall_time": getattr(
                                record,
                                "dequeued_wall_time",
                                None,
                            ),
                        },
                    },
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
                        "path": self.redaction.Sensitive(
                            record.pathname,
                            self.path_redactor,
                            "record.pathname",
                        ),
                        "line": record.lineno,
                    },
                },
                "exception": {
                    "traceback": _logrecord_exception_to_dict(record),
                    "stack": (
                        self.redaction.Sensitive(
                            self.formatStack(record.stack_info).splitlines(),
                            self.path_redactor,
                            "record.stack_info",
                        )
                        if record.stack_info
                        else None
                    ),
                    "text": record.exc_text,
                },
            },
            "extra": extras,
            "message": (
                message.splitlines() if self.splitlines_message else message
            ),
        }

        # processed_time is useful to measure how long it took do transfer,
        # dequeue and process the eventual callbacks when comparing to
        # `relativeCreated`
        struct_log["context"]["dynamic"]["statistics"][
            "processed_wall_time"
        ] = import_lazy("time").time()
        return import_lazy("json").dumps(
            struct_log,
            default=import_lazy_project("redaction").safe_string_json_redacted,
            indent=self.json_indent,
        )

    def _render_extras_compact(self, extras: dict[str, Any]) -> str:
        """Render extras in compact format with key: value pairs.

        Args:
            extras: The extra fields to render.

        Returns:
            A joined string of formatted extras using the configured separator.
        """
        sep = self.human_extra_message_sep
        return sep.join(
            f"{key}: "
            + (str(value) if self.pprint is None else self.pprint(value))
            for key, value in extras.items()
        )

    def _render_extras_verbose(self, extras: dict[str, Any]) -> str:
        """Render extras in verbose format using only values.

        Args:
            extras: The extra fields to render.

        Returns:
            A joined string of extra values using the configured separator.
        """
        sep = self.human_extra_message_sep
        return sep.join(str(value) for value in extras.values())

    def _format_human_readable(
        self, record: LogRecord, extras: dict[str, Any]
    ) -> str:
        """Format a LogRecord into human-readable format.

        Args:
            record: The log record to format.
            extras: A dictionary of extra fields extracted from the record.

        Returns:
            A formatted string suitable for terminal or plain file output.
        """
        message = super().format(record)
        if not extras or not self.human_extra:
            return message

        rendered = (
            self._render_extras_compact(extras)
            if self.compact_extras
            else self._render_extras_verbose(extras)
        )
        return message + self.human_extra_message_sep + rendered

    @override
    def format(self, record: LogRecord) -> str:
        """Format a record.

        Example:
            >>> import sys
            >>>
            >>> JSONFormatter().format(
            >>>     LogRecord(
            >>>         "dummy",
            >>>         0,
            >>>         "dummy",
            >>>         0,
            >>>         "dummy",
            >>>         None,
            >>>         None,
            >>>     )
            >>> )
            { ... }
            >>> JSONFormatter().format(
            >>>     LogRecord(
            >>>         "dummy",
            >>>         0,
            >>>         "dummy",
            >>>         0,
            >>>         "dummy",
            >>>         None,
            >>>         sys.exc_info(),
            >>>     )
            >>> )
            { ... }

        Args:
            record: the record to format.

        Returns:
            a JSON string representing the record.
        """
        extras = self._extract_extras(record)
        if is_true(boolean=self.structured):
            return self._format_structured(record, extras)

        return self._format_human_readable(record, extras)
