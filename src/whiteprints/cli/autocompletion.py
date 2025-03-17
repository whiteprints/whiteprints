# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Autocompletion management."""

import importlib
from argparse import ArgumentParser


def argcomplete(parser: ArgumentParser) -> None:
    """Add autocompletion to the parser.

    Does nothing if argcomplete is not installed.
    """
    importlib.import_module("argcomplete").autocomplete(parser)
