# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
import os
import sys
from typing import Final


__all__: Final = []
"""Public module attributes."""


def _setup_package() -> None:
    """Setup the package.

    The behaviour of the program is the following:
        * On debug (__debug__ == True), we activate beartype for runtime type
        checking and disable all sigint handling.
        * On release (__debug__ == False), we disable beartype and activate
        sigint handling.

    Then environement variables are imported from a dotenv file.
    """
    if __debug__:
        importlib.import_module("beartype.claw").beartype_this_package()
    else:
        importlib.import_module(
            "whiteprints.signals",
            __package__,
        ).exit_gracefully_on_sigint()

    environment = importlib.import_module(
        "whiteprints.environment",
        __package__,
    )
    environment.load_dotenv(environment.ENVIRONMENT_FILE)


def _gracefully_setup_package() -> None:
    """Setup the package.

    The behaviour of the program is the following:
        * On debug (__debug__ == True), we activate beartype for runtime type
        checking and disable all sigint handling.
        * On release (__debug__ == False), we disable beartype and activate
        sigint handling.

    Then environement variables are imported from a dotenv file.

    Fails gracefully on error.
    """
    try:
        _setup_package()
    except BaseException:
        logger = importlib.import_module("logging").getLogger("entrypoint")
        logger.exception(
            "Fatal Error. Something went wrong while seting up the package."
        )
        sys.exit(os.EX_SOFTWARE)


_gracefully_setup_package()
