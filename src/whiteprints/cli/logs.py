# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging configuration for the CLI."""

import importlib
import logging
import sys
from typing import Final, Literal, TextIO

from whiteprints import console
from whiteprints.loc import _


__all__: Final = ["LogLevel", "configure_logging"]


if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias


LogLevel: TypeAlias = Literal[
    "CRITICAL",
    "ERROR",
    "WARNING",
    "INFO",
    "DEBUG",
    "NOTSET",
]


def configure_logging(
    level: LogLevel,
    *,
    file: TextIO,
    log_format: str = _(
        "[{process}:{thread}] [{pathname}:{funcName}:{lineno}]\n{message}",
    ),
    date_format: str = _("[%Y-%m-%dT%H:%M:%S]"),
) -> None:
    """Configure Rich logging handler.

    Args:
        level: The logging verbosity level.
        file: An optional file in which to log.
        log_format: The log message format.
        date_format: The log date format.

    Example:
        >>> import sys
        >>>
        >>> configure_logging("INFO", file=sys.stderr)
        None

    See Also:
        https://rich.readthedocs.io/en/stable/logging.html
    """
    rich_traceback = importlib.import_module("rich.traceback")
    suppress = []

    rich_traceback.install(
        show_locals=True,
        suppress=suppress,
    )
    handlers = [
        importlib.import_module("rich.logging").RichHandler(
            console=console.STDERR,
        )
        if file.name == "-"
        else logging.StreamHandler(file),
    ]

    logging.basicConfig(
        format=f"{log_format}",
        handlers=handlers,
        level=level.upper(),
        datefmt=date_format,
        style="{",
    )
    logging.captureWarnings(capture=True)
