# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The app metadata."""

import importlib
from functools import cache
from re import Pattern
from typing import Final


__all__: Final = ["app_name"]


@cache
def valid_slug_pattern() -> Pattern[str]:
    """Create a pattern representing a valid slug.

    Returns:
        a pattern that represents a valid slug.
    """
    return importlib.import_module("re").compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def is_valid_slug(slug: str) -> bool:
    """Check if a slug is valid.

    Args:
        slug:
            The slug candidate name.

    Example:
        >>> is_valid_slug("whiteprints")
        True
        >>> is_valid_slug("-bad slug")
        False

    Returns:
        True if the slug name is valid, False otherwise.
    """
    return bool(valid_slug_pattern().fullmatch(slug))


@cache
def app_name() -> str:
    """The name of the application.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Returns:
        The name of the application.
    """
    app_name = "whiteprints"
    assert is_valid_slug(app_name), (
        f"{app_name} is not a valid application name. It should be a "
        "valid slug."
    )
    return app_name
