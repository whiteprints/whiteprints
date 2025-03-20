# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

import importlib
import os
import sys
from argparse import (
    ArgumentError,
    ArgumentParser,
    ArgumentTypeError,
    Namespace,
)
from pathlib import Path
from typing import Final, Optional

from whiteprints import _


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
    except (ArgumentError, ArgumentTypeError) as argument_error:
        importlib.import_module("whiteprints", __package__).stderr().print(
            argument_error
        )
        sys.exit(os.EX_USAGE)

    return namespace


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Example:
        >>> try:
        >>>     entrypoint()
        >>> except SystemExit:
        >>>     pass
        ...

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.
    """
    entrypoint_parser = importlib.import_module(
        "whiteprints.cli.entrypoint_parser",
        __package__,
    ).create_entrypoint_parser()
    subparser = entrypoint_parser.add_subparsers(
        title=_("Subcommands"),
        dest="cmd",
    )
    importlib.import_module(
        "whiteprints.cli.command.init_parser",
        __package__,
    ).init_parser(subparser, entrypoint_parser)

    with importlib.import_module("contextlib").suppress(ModuleNotFoundError):
        importlib.import_module("argcomplete").autocomplete(
            entrypoint_parser,
            exit_method=sys.exit,
            always_complete_options="long",
        )

    namespace = _parse_args(entrypoint_parser, args)
    if namespace.cmd is None:
        entrypoint_parser.print_help()
        sys.exit(os.EX_OK)

    importlib.import_module(
        "whiteprints.cli.logs",
        __package__,
    ).setup_logging(
        Path(namespace.log_config) if namespace.log_config else None,
    )
    logger = importlib.import_module("logging").getLogger(__name__)
    logger.debug(
        "program started",
        extra={
            "debug_info": (
                lambda: (
                    importlib.import_module(
                        "whiteprints.debug_info",
                        __package__,
                    ).gather_debug_info()
                )
            ),
            "namespace": namespace.__dict__,
        },
    )
    command = importlib.import_module(
        f"whiteprints.cli.command.{namespace.cmd}",
        __package__,
    )
    getattr(command, namespace.cmd)(namespace)
