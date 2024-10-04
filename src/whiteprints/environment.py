# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Manage environment variables."""

import logging
from pathlib import Path
from typing import Final

import dotenv


__all__: Final = ["ENVIRONMENT_FILE", "load_dotenv"]

ENVIRONMENT_FILE: Final = Path(".env")
"""The default path to the dotenv file."""


def load_dotenv(environment_file: Path) -> None:
    """Load a dotenv file to os.environ.

    A dotenv file stores the environment variables useful to customise the
    behaviour of the app.

    Args:
        environment_file: the dotenv file to load.
    """
    if dotenv.load_dotenv(environment_file):
        logging.getLogger(__name__).info(
            "Loading environment variables from `%s` file.", environment_file
        )
