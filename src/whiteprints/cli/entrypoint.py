# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command Line Interface app entrypoint."""

import importlib
import os
import sys
from typing import Final, Optional


__all__: Final = ["entrypoint"]
"""Public module attributes."""


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
        namespace = entrypoint_parser.parse_args(args)
        importlib.import_module(
            "whiteprints.cli.logs",
            __package__,
        ).setup_logging(
            namespace.log_conf,
        )
    except Exception:
        # Because the error occured before the logger is set-up the following
        # exceptions here are probably not properly formatted.
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception("Something went wrong while setting up the program.")
        sys.exit(os.EX_SOFTWARE)
