# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The app metadata."""

import importlib
from functools import cache
from typing import Final


__all__: Final = ["app_name"]


@cache
def app_name() -> str:
    """The name of the application.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Returns:
        The name of the application.
    """
    return importlib.import_module(
        "whiteprints.cli.exception",
        __package__,
    ).check_app_name("whiteprints")
