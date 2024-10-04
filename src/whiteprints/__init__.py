# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

from typing import Final

from whiteprints.environment import ENVIRONMENT_FILE, load_dotenv
from whiteprints.package_metadata import __version__


__all__: Final = ["__version__"]
"""Public module attributes."""


load_dotenv(ENVIRONMENT_FILE)
