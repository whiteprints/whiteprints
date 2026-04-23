# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The debug subcommand."""

from argparse import ArgumentParser, Namespace


def debug(parser: ArgumentParser, _namespace: Namespace) -> None:
    """Does nothing."""
    parser.print_help()
