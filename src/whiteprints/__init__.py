# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
from typing import Final

from whiteprints.environment import ENVIRONMENT_FILE, load_dotenv
from whiteprints.package_metadata import __version__


__all__: Final = ["__version__"]
"""Public module attributes."""


if __debug__:
    beartype = importlib.import_module("beartype")
    beartype_claw = importlib.import_module("beartype.claw")
    beartype_claw.beartype_this_package(
        conf=beartype.BeartypeConf(is_color=False),
    )


load_dotenv(ENVIRONMENT_FILE)
