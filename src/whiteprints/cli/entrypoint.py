# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

import importlib
import os
import sys
from argparse import ArgumentError, ArgumentParser, Namespace
from typing import Final, Optional


__all__: Final = ["entrypoint"]
"""Public module attributes."""


def _parse_args(
    parser: ArgumentParser,
    args: Optional[list[str]],
) -> Namespace:
    """Parse the arguments.

    Print an error and exit on parsing error.

    Args:
        parser: the entrypoint argument parser
        args: the arguments to parse

    Returns:
        an argument namespace.
    """
    try:
        namespace = parser.parse_args(args)
    except ArgumentError as argument_error:
        importlib.import_module(
            "whiteprints.console", __package__
        ).stderr().print(argument_error)
        sys.exit(os.EX_USAGE)

    return namespace


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.
    """
    try:
        entrypoint_parser = importlib.import_module(
            "whiteprints.cli.entrypoint_parser",
            __package__,
        ).create_entrypoint_parser()
        importlib.import_module("argcomplete").autocomplete(entrypoint_parser)
        namespace = _parse_args(entrypoint_parser, args)
        importlib.import_module(
            "whiteprints.cli.logs",
            __package__,
        ).setup_logging(
            namespace.log_conf,
        )
    except Exception:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception("Fatal Error")
        sys.exit(os.EX_SOFTWARE)
