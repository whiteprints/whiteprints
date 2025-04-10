# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

import importlib
import os
import sys
from pathlib import Path
from typing import Final, Optional

from whiteprints import LOCALE_DIRECTORY, _


__all__: Final = ["entrypoint"]
"""Public module attributes."""


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Example:
        >>> import os
        >>>
        >>> try:
        >>>     entrypoint()
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
        importlib.import_module("argcomplete").autocomplete(entrypoint_parser)

    namespace = entrypoint_parser.parse_args(args)
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
    logger.debug("program finished without errors")
