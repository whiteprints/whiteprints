# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Final


__all__: Final = [
    "DISTRIBUTION_NAME",
    "FALSE_SET",
    "TRUE_SET",
    "is_true",
]
"""Public module attributes."""


DISTRIBUTION_NAME: Final = "whiteprints"
"""The normalized distribution name (no space, no underscores, lowercase).

The distribution name is different from the import name.
See https://packaging.python.org/en/latest/discussions/distribution-package-vs-import-package/
"""


FALSE_SET: Final = ("0", "false", "no", "n", "f")
"""Valid False strings."""

TRUE_SET: Final = ("1", "true", "yes", "y", "t")
"""Valid True strings."""


def is_true(*, boolean: str | bool) -> bool:
    """Check if a boolean string is true.

    Args:
        boolean: the boolean string to check.

    Returns:
        True if the boolean string is considered true, False otherwise.
    """
    return str(boolean).lower() in TRUE_SET
