# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Autocompletion management."""

import importlib
from argparse import ArgumentParser
from functools import cache


@cache
def argcomplete_installed() -> bool:
    """Test if the `argcomplete` module is installed.

    Returns:
        True if `argcomplete` is installed, False otherwise.
    """
    try:
        importlib.import_module("argcomplete")
    except ImportError:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.info(
            "No autocompletion available (argcomplete is not installed)"
        )
        return False

    return True


def argcomplete(parser: ArgumentParser) -> None:
    """Add autocompletion to the parser.

    Does nothing if argcomplete is not installed.
    """
    if argcomplete_installed():
        argcomplete = importlib.import_module("argcomplete")
        argcomplete.autocomplete(parser)
