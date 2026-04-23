# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
from functools import cache
from types import ModuleType
from typing import Final


__all__: Final = [
    "has_extra",
    "import_extra",
    "import_lazy",
    "import_lazy_project",
]
"""Public module attributes."""


@cache
def import_lazy(module_name: str) -> ModuleType:
    """Import a module and cache it.

    Args:
        module_name: the name of the module to import, as it would be done with
            `importlib.import_module`. Always use absolute import name.

    Returns:
        The requested module.
    """
    # Here importlib needs to be imported at top-level (bootstraping).
    signals_handler = importlib.import_module("whiteprints.signals_handler")
    with signals_handler.DelaySignals():
        return importlib.import_module(module_name)


def import_lazy_project(module_name: str) -> ModuleType:
    """Import a project submodule and cache it.

    Args:
        module_name: the name of the module to import, relative to the project
        root module.

    Note:
        This will break if running 'python __init__.py', but that's discouraged
        usage of a package.

    Returns:
        The requested module.
    """
    return import_lazy(f"{__package__}.{module_name}")


@cache
def import_extra(module_name: str) -> ModuleType | None:
    """Import a plugin module.

    Args:
        module_name: the name of the module to import, as it would be done with
            `importlib.import_module`. Always use absolute import name.

    Returns:
        None if the module is not found, otherwise returns the requested
        module.
    """
    try:
        return import_lazy(module_name)
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
