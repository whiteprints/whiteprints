# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import importlib
from functools import cache, cached_property
from pathlib import Path
from types import ModuleType
from typing import Callable, Final, Optional


__all__: Final = ["_", "has_module", "maybe_import_module"]
"""Public module attributes."""


class LazyGettext:
    """Lazily initializes gettext translation when first used.

    This class provides a callable `_` object that behaves like a standard
    gettext translation function but defers loading translation files
    until the first actual call.
    """

    def __init__(
        self,
        locale_directory: Optional[Path] = None,
        *,
        fallback: bool = True,
    ) -> None:
        """Initializes the LazyGettext instance.

        Args:
            locale_directory: Path to the directory containing locale files.
                Set to None to disable translation.
            fallback: use a fallback if translation is not found.
        """
        self.locale_directory = locale_directory
        self.fallback = fallback

    @cached_property
    def __call__(self) -> Callable[[str], str]:
        """Performs the actual import and binding of gettext translation.

        Returns:
            The gettext translation function.
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
def maybe_import_module(module_name: str) -> Optional[ModuleType]:
    """Import a module.

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


def has_module(module_name: str) -> bool:
    """Import a module.

    Args:
        module_name: the name of the module to import, as it would be done with
        `importlib.import_module`. Always use absolute import name.

    Returns:
        True if the module is importable, False otherwise
    """
    return maybe_import_module(module_name) is not None


def _setup_package() -> None:
    """Setup the package.

    Load the modules dotenv and beartype if found.

    Example:
        >>> _setup_package()
        None
    """
    if (claw := maybe_import_module("beartype.claw")) is not None:
        claw.beartype_this_package()

    if (dotenv := maybe_import_module("dotenv")) is not None:
        dotenv.load_dotenv()


_setup_package()

_: Final = LazyGettext(Path(__file__).parent / "locale")
"""A Gettext translation."""
