# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Manage a global rich console."""

from functools import cache
from typing import Final

from rich.console import Console


__all__: Final = ["stderr", "stdout"]
"""Public module attributes."""


@cache
def stdout() -> Console:
    """A high level console interface instance.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    See Also:
        https://rich.readthedocs.io/en/stable/reference/console.html

    Returns:
        A rich console printing to the standard output.
    """
    return Console(soft_wrap=True)


@cache
def stderr() -> Console:
    """A high level console interface instance.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    See Also:
        https://rich.readthedocs.io/en/stable/reference/console.html

    Returns:
        A rich console printing to the standard error.
    """
    return Console(stderr=True, soft_wrap=True)
