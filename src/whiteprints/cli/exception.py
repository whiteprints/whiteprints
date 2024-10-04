# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command-Line Interface user defined exceptions."""

import re
from typing import Final


__all__: Final = [
    "InvalidAppNameError",
    "check_app_name",
    "is_valid_slug",
]


class InvalidAppNameError(ValueError):
    """The application name is invalid."""

    def __init__(self, app_name: str) -> None:
        """Initialize the exception."""
        super().__init__(
            f"{app_name} is not a valid application name. It should be a "
            "valid slug."
        )


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
    return bool(re.fullmatch(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", slug))


def check_app_name(app_name: str) -> str:
    """Check whether an app name is a valid slug.

    This function is the identity if the app name is a valid slug.

    Args:
        app_name:
            The app name.

    Example:
        >>> check_app_name("valid-app-name")
        'valid-app-name'

    Raises:
        InvalidAppNameError: The app name is not a valid slug.

    Returns:
        The app name.
    """
    if __debug__ and not is_valid_slug(app_name):
        raise InvalidAppNameError(app_name)

    return app_name
