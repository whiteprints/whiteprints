# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
import os
from collections.abc import Callable
from functools import cache, cached_property
from types import ModuleType
from typing import Final


__all__: Final = ["_", "has_extra", "import_extra"]
"""Public module attributes."""


class LazyGettext:
    """Lazily initializes gettext translation when first used.

    If no locale directory is given, no localization is performed.

    This class provides a callable `_` object that behaves like a standard
    gettext translation function but defers loading translation files
    until the first actual call.

    Example:
        >>> _ = LazyGettext()
        >>> _("No localization is performed")
        No localization is performed
    """

    def __init__(
        self,
        locale_directory: str | None = None,
        *,
        fallback: bool = True,
    ) -> None:
        """Initializes the LazyGettext instance.

        Args:
            locale_directory: path
            fallback: use a fallback if translation is not found.
        """
        self.locale_directory = locale_directory
        self.fallback = fallback

    @cached_property
    def __call__(self) -> Callable[[str], str]:
        """Performs the actual import and binding of gettext translation.

        Returns:
            The gettext translation function.

        Example:
            >>> _ = LazyGettext()
            >>> _("test")
            test
            >>> _ = LazyGettext("path/to/locale")
            >>> _("test")
            ...
        """
        if self.locale_directory is None:
            return lambda x: x

        return (
            importlib.import_module("gettext")
            .translation(
                __name__,
                self.locale_directory,
                fallback=self.fallback,
            )
            .gettext
        )


@cache
def import_extra(module_name: str) -> ModuleType | None:
    """Import a plugin module.

    Args:
        module_name: the name of the module to import, as it would be done with
            `importlib.import_module`. Always use absolute import name.

    Returns:
        None if the module is not found, otherwise returns the module.
    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None


def has_extra(module_name: str) -> bool:
    """Check if a plugin is installed.

    Args:
        module_name: the name of the module to import, as it would be done with
            `importlib.import_module`. Always use absolute import name.

    Returns:
        True if the module is importable, False otherwise
    """
    return import_extra(module_name) is not None


@cache
def _setup_package(
    *,
    claw: ModuleType | None = None,
    dotenv: ModuleType | None = None,
) -> None:
    """Setup the package.

    Load the modules dotenv and beartype if given.

    Example:
        >>> _setup_package()
        None
    """
    if claw is not None:
        claw.beartype_this_package()

    if dotenv is not None:
        dotenv.load_dotenv()


_setup_package(
    claw=import_extra("beartype.claw"),
    dotenv=import_extra("dotenv"),
)

_: Final = LazyGettext(os.path.join(os.path.dirname(__file__), "locale"))
"""A Gettext translation."""
