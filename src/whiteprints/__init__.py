# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
from functools import cache
from types import ModuleType
from typing import Final


__all__: Final = []
"""Public module attributes."""


@cache
def _setup_package(
    *,
    claw: ModuleType | None = None,
) -> None:
    """Setup the package.

    Load beartype if not None.

    Example:
        >>> _setup_package()
        None
    """
    if claw is not None:
        claw.beartype_this_package()


try:
    _setup_package(
        claw=importlib.import_module("beartype.claw"),
    )
except ImportError:
    _setup_package()
