# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'debug' subcommand."""

from argparse import ArgumentParser
from typing import Final

from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy_project


__all__: Final = ["setup_debug_parser"]
"""Public module attributes."""


def setup_debug_parser(parser: ArgumentParser) -> None:
    """Debug information.

    Args:
        parser: the main parser use to forward the `formatter_class`.

    Example:
        >>> main_parser = ArgumentParser()
        >>> subparsers = main_parser.add_subparsers()
        >>> setup_debug_parser(subparsers.add_parser("debug", add_help=False))
        None
    """
    parser.add_argument(
        "-p",
        "--platform",
        action=import_lazy_project("cli.command.debug_parser_action").Platform,
        nargs="?",
        const="redact",
        choices=("redact", "reveal"),
        help=_("Show platform and environment information and exit."),
    )
    parser.add_argument(
        "-d",
        "--distributions",
        action=import_lazy_project(
            "cli.command.debug_parser_action"
        ).Distributions,
        nargs="?",
        const="redact",
        choices=("redact", "reveal"),
        help=_("Show program distributions and exit."),
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help=_("Show this help message and exit."),
    )
