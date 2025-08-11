# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Filesystem helpers for Whiteprints logging."""

from functools import cache
from typing import Final

from whiteprints.lazy_import import import_extra, import_lazy_project
from whiteprints.package_constants import DISTRIBUTION_NAME


__all__: Final = [
    "user_log_dir",
]


@cache
def user_log_dir() -> str:
    """Return the default user log directory path.

    Uses `platformdirs.user_log_dir`. Falls back to a temp directory if
    platformdirs is missing.

    Returns:
        Path to the user log directory, or a temp dir if `platformdirs`
        is unavailable.
    """
    if (platformdirs := import_extra("platformdirs")) is None:
        return import_lazy_project("directories_provider").make_temp_dir(
            "logs"
        )

    return platformdirs.user_log_dir(DISTRIBUTION_NAME)
