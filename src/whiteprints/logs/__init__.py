# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Everything related to logging."""

import os
from typing import Final

from whiteprints.package_constants import DISTRIBUTION_NAME, is_true


__all__: Final = ["use_struct_logs"]
"""Public module attributes."""


def use_struct_logs() -> bool:
    """Check whether structured logs should be used.

    Returns:
        True if structured logs should be used, False otherwise.
    """
    return is_true(
        boolean=os.getenv(f"{DISTRIBUTION_NAME.upper()}_LOG_STRUCT", "")
    )
