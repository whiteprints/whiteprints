# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Everything related to the command line interface."""

from typing import Final

from whiteprints.cli import exception


__all__: Final = ["APP_NAME", "__app_name__"]

__app_name__: Final = "whiteprints"
"""The name of the application."""

APP_NAME = exception.check_app_name(__app_name__).replace("-", "_").upper()
"""The name of the application in capital letters."""
