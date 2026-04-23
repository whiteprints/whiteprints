# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration-loading utilities for Whiteprints logging."""

from collections.abc import Mapping
from typing import Final, Literal

from whiteprints.cli.logs.logging_exceptions import (
    BooleanError,
    LogLevelError,
    LogStreamError,
)
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString


__all__: Final = [
    "env_log_level",
    "env_log_stream",
    "env_structured_logs",
]


def env_log_level(
    env: Mapping[str, SafeString],
    default_level: Literal[
        "NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    ] = "CRITICAL",
) -> SafeString | str:
    """Resolve and validate the log level from environment variables.

    Args:
        env: Mapping of environment variables.
        default_level: Default level name if none is specified.

    Returns:
        The validated uppercase log level string.

    Raises:
        LogLevelError: If the specified level is invalid.
    """
    redaction = import_lazy_project("redaction")
    prefix = DISTRIBUTION_NAME.upper()
    level_name = env.get(
        f"{prefix}_LOG_LEVEL",
        redaction.Clear(default_level, "default"),
    )

    if str.isdigit(level_name.reveal):
        logging = import_lazy("logging")
        level_value = int(level_name.reveal)
        if level_value not in logging.getLevelNamesMapping().values():
            raise LogLevelError(level_name)

        return logging.getLevelName(level_value)

    return level_name


def env_structured_logs(
    env: Mapping[str, SafeString],
    default_structured: Literal["true", "false"] = "false",
) -> SafeString | str:
    """Structured logs owercased boolean string.

    Args:
        env: Environment mapping.
        default_structured: Default if not provided.

    Returns:
        'true' or 'false' based on env.

    Raises:
        BooleanError: If the env value is not a recognized boolean.
    """
    redaction = import_lazy_project("redaction")
    structured = env.get(
        f"{DISTRIBUTION_NAME.upper()}_LOG_STRUCT",
        redaction.Clear(default_structured, "default"),
    )

    true_set = import_lazy_project("package_constants").TRUE_SET
    false_set = import_lazy_project("package_constants").FALSE_SET
    if structured.reveal not in (true_set + false_set):
        raise BooleanError(structured)

    return structured


def env_log_stream(
    env: Mapping[str, SafeString],
    default_log_stream: Literal[
        "ext://sys.stderr",
        "ext://sys.stdout",
    ] = "ext://sys.stderr",
) -> SafeString | str:
    """Return a string suitable for dictConfig's "stream" field.

    Args:
        env: Environment mapping.
        default_log_stream: Default stream name.

    Returns:
        'ext://sys.stdout' or 'ext://sys.stderr' based on env.

    Raises:
        LogStreamError: If the env value is not 'stdout' or 'stderr'.
    """
    prefix = DISTRIBUTION_NAME.upper()
    redaction = import_lazy_project("redaction")
    log_stream = env.get(
        f"{prefix}_LOG_STREAM",
        redaction.Clear(default_log_stream, "default"),
    )

    if log_stream not in {"ext://sys.stdout", "ext://sys.stderr"}:
        raise LogStreamError(log_stream)

    return log_stream
