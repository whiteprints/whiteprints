# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

import contextlib
import importlib
import importlib.metadata
import sys
from functools import cache
from pathlib import Path
from typing import Final, Optional

from whiteprints import LOCALE_DIRECTORY, _


__all__: Final = ["entrypoint", "prog_name"]
"""Public module attributes."""


@cache
def prog_name() -> str:
    """Determine the program name from the entrypoint metadata.

    Returns:
        The program name
    """
    entrypoints = importlib.metadata.entry_points()
    entrypoint_value = f"{__name__}:entrypoint"

    if sys.version_info >= (3, 10):
        return entrypoints.select(
            group="console_scripts",
            value=entrypoint_value,
        ).names.pop()

    return next(
        entrypoint.name
        for entrypoint in entrypoints["console_scripts"]
        if entrypoint.value == entrypoint_value
    )


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Example:
        >>> import os
        >>>
        >>> try:
        >>>     entrypoint([])
        >>> except SystemExit as ext:
        >>>     assert ext.code == os.EX_OK
        ...

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.
    """
    gettext = importlib.import_module("gettext")
    gettext.bindtextdomain(
        "argparse",
        LOCALE_DIRECTORY,
    )
    gettext.textdomain("argparse")

    entrypoint_parser = importlib.import_module(
        "whiteprints.cli.entrypoint_parser",
        __package__,
    ).create_entrypoint_parser(prog_name())

    subparsers = entrypoint_parser.add_subparsers(
        title=_("Subcommands"),
        dest="cmd",
    )
    importlib.import_module(
        "whiteprints.cli.command.init_parser",
        __package__,
    ).setup_init_parser(
        subparsers.add_parser(
            "init",
            formatter_class=entrypoint_parser.formatter_class,
            description=_("Initialize a Python project."),
            help=_("Initialize a Python project."),
            exit_on_error=False,
            add_help=False,
            epilog=_(
                "Note: see https://copier.readthedocs.io/en/stable/configuring/"
                " for help on how to use Copier and COPIER_ARGS (optional)."
            ),
        )
    )

    with contextlib.suppress(ModuleNotFoundError):
        importlib.import_module("argcomplete").autocomplete(entrypoint_parser)

    namespace = entrypoint_parser.parse_args(args)
    importlib.import_module("whiteprints.cli.entrypoint_parser").resolve_flags(
        entrypoint_parser, namespace
    )

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
    logger.debug("program finished without errors")
