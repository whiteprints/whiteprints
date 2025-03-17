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


def _setup_parser() -> ArgumentParser:
    try:
        entrypoint_parser = importlib.import_module(
            "whiteprints.cli.entrypoint_parser",
            __package__,
        ).create_entrypoint_parser()
        importlib.import_module(
            "whiteprints.cli.autocompletion",
            __package__,
        ).argcomplete(entrypoint_parser)
    except Exception:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception(
            "Fatal Error. Something went wrong while setting up the program."
        )
        sys.exit(os.EX_SOFTWARE)

    return entrypoint_parser


def _parse_args(
    parser: ArgumentParser,
    args: Optional[list[str]],
) -> Namespace:
    try:
        namespace = parser.parse_args(args)
    except ArgumentError as argument_error:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        importlib.import_module(
            "whiteprints.console", __package__
        ).stderr().print(argument_error)
        sys.exit(os.EX_SOFTWARE)
    except Exception:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception(
            "Fatal Error. Something went wrong while setting up the program."
        )
        sys.exit(os.EX_SOFTWARE)

    return namespace


def _setup_logging(namespace: Namespace) -> None:
    try:
        importlib.import_module(
            "whiteprints.cli.logs",
            __package__,
        ).setup_logging(
            namespace.log_conf,
        )
    except Exception:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception(
            "Fatal Error. Something went wrong while setting up the program."
        )
        sys.exit(os.EX_SOFTWARE)


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.
    """
    entrypoint_parser = _setup_parser()
    namespace = _parse_args(entrypoint_parser, args)
    _setup_logging(namespace)
