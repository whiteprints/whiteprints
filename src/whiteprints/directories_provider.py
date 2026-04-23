# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Global persistent directories."""

from functools import cache
from typing import Final, TypeVar

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString


__all__: Final = ["make_temp_dir"]
"""Public module attributes."""


T = TypeVar("T")


@cache
def make_temp_dir(prefix: str) -> SafeString:
    """Return a temporary directory path for logs.

    Creates a new temp directory with the pattern:
        "{prefix}_{DISTRIBUTION_NAME}_<random>".

    Args:
        prefix: Prefix for the temporary directory name.

    Returns:
        The path to the temporary log directory.
    """
    redaction = import_lazy_project("redaction")
    return redaction.Sensitive(
        import_lazy("tempfile").mkdtemp(
            prefix=f"{prefix}{'_' if prefix else ''}{DISTRIBUTION_NAME}_"
        ),
        import_lazy_project("redactor").PathRedactor(),
        "tempfile.mkdtemp",
    )
