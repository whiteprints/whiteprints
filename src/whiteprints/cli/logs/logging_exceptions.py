# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exception types for Whiteprints logging configuration."""

from typing import Final

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy
from whiteprints.redaction import SafeString


__all__: Final = [
    "BooleanError",
    "FallbackError",
    "LogLevelError",
    "LogStreamError",
    "LoggingConfigurationError",
    "RecursiveFallbackError",
    "SpawnLoggerWorkerError",
    "TemplateSubstitutionError",
]


class LoggingConfigurationError(WhiteprintsError):
    """Base exception for logging configuration failures."""


class SpawnLoggerWorkerError(WhiteprintsError):
    """Logger worker spawn failed."""

    def __init__(self) -> None:
        """Init error when spawning a logger worker failed."""
        super().__init__(_("Failed to spawn logger worker."))


class LoadingConfigurationError(LoggingConfigurationError):
    """Loadding configuration with dictConfig failed."""

    def __init__(self, path: SafeString | None = None) -> None:
        super().__init__(
            _("Loading configuration{} failed").format(
                "" if path is None else _(" from file {}").format(path)
            )
        )
        self.path = path


class RecursiveFallbackError(WhiteprintsError):
    """Raised when fallback configuration exceeds safe recursion depth."""

    def __init__(self, max_depth: int) -> None:
        """Init error when the fallback depth limit is exceeded.

        Args:
            max_depth: The maximum allowed fallback depth before bailing.
        """
        super().__init__(
            _(
                "Exceeded safe fallback configuration depth (limit: {})."
            ).format(max_depth)
        )
        self.max_depth = max_depth


class LogLevelError(LoggingConfigurationError):
    """Raised when the specified log level is invalid.

    The error message lists all valid log levels for reference.
    """

    def __init__(self, log_level: SafeString, pad: int = 10) -> None:
        """Init error for invalid log level.

        Args:
            log_level: The invalid log level input.
            pad: Width for alignment in message formatting.
        """
        valid_log_levels = import_lazy("logging").getLevelNamesMapping()
        super().__init__(
            _(
                "Invalid log level: '{}'\n"
                "Valid levels (case insensitive):\n"
                " {}"
            ).format(
                log_level,
                "\n ".join(
                    (
                        f"'{level_name}'"
                        f"{' ' * (pad - len(level_name))}({level_value})"
                    )
                    for level_name, level_value in valid_log_levels.items()
                ),
            )
        )
        self.log_level = log_level
        self.valid_log_levels = valid_log_levels


class LogStreamError(LoggingConfigurationError):
    """Raised when the log stream value is invalid."""

    def __init__(self, log_stream: SafeString) -> None:
        """Init error for invalid log stream.

        Args:
            log_stream: The invalid log stream value.
        """
        super().__init__(
            _(
                "Invalid log stream: '{}'\n"
                "Valid log streams are 'STDOUT' or 'STDERR'"
            ).format(log_stream)
        )
        self.log_stream = log_stream


class BooleanError(LoggingConfigurationError):
    """Raised when a boolean environment variable value is invalid."""

    def __init__(self, boolean: SafeString, pad: int = 4) -> None:
        """Init error for invalid boolean value.

        Args:
            boolean: The invalid boolean string.
            pad: Width for alignment in message formatting.
        """
        true_set = import_lazy("whiteprints").TRUE_SET
        false_set = import_lazy("whiteprints").FALSE_SET

        super().__init__(
            _(
                "Invalid boolean: {}.\nValid booleans (case insensitive):\n {}"
            ).format(
                boolean,
                "\n ".join(
                    (f"'{true}'{' ' * (pad - len(true))} or '{false}'")
                    for true, false in zip(true_set, false_set, strict=True)
                ),
            )
        )
        self.boolean = boolean


class TemplateSubstitutionError(LoggingConfigurationError):
    """Raised when a template placeholder is missing during substitution."""

    def __init__(self, missing_key: str) -> None:
        """Init error for missing template key.

        Args:
            missing_key: Placeholder key not found in context.
        """
        super().__init__(
            _("Missing placeholder in template: {}").format(missing_key)
        )
        self.missing_key = missing_key


class FallbackError(LoggingConfigurationError):
    """Raised when fallback configuration also fails."""

    def __init__(self) -> None:
        """Init error when fallback logging config fails.

        Args:
            configuration_error: The original config error raised.
        """
        super().__init__(_("Fallback configuration failed."))
