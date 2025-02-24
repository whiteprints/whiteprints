# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

from typing import Final

from beartype.claw import beartype_this_package

from whiteprints.environment import ENVIRONMENT_FILE, load_dotenv
from whiteprints.package_metadata import __version__


__all__: Final = ["__version__"]
"""Public module attributes."""

beartype_this_package()

load_dotenv(ENVIRONMENT_FILE)
