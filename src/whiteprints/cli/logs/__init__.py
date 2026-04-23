# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging system configurator for Whiteprints CLI.

All sibling modules are imported dynamically via importlib.import_module()
to avoid any static “from” or “import” statements that could cause cycles.
"""

from functools import cache
from typing import TYPE_CHECKING, Final, Literal

from whiteprints.cli.logs.logging_config import Logging
from whiteprints.concurrency import is_main_process
from whiteprints.lazy_import import import_lazy_project


__all__: Final = ["LOGGING", "is_main_process"]


@cache
def __getattr__(name: Literal["LOGGING"]) -> Logging:
    """Global logging configurator instance for Whiteprints CLI.

    Returns:
        A Logging instance.

    Raises:
        AttributeError: name is not importable.
    """
    if name == "LOGGING":
        return import_lazy_project("cli.logs.logging_config").Logging(
            capture_warnings=True
        )

    raise AttributeError(name)


if TYPE_CHECKING:
    LOGGING: Logging
