# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Backaport of importlib.metadata.packages_distributions for Python 3.9."""

import collections
import inspect
from collections.abc import Iterable
from importlib.metadata import Distribution, PackagePath, distributions
from typing import Any, Final, Optional


__all__: Final = ["packages_distributions"]


def packages_distributions() -> dict[str, list[str]]:
    """Best effort backport of `packages_distributions`.

    We do not use importlib_metadata as this is a horrible piece of
    sofware engineering which monkeypatches the Python standard library.

    Returns:
        A mapping of top-level packages to their distributions.
    """
    pkg_to_dist: dict[str, list[str]] = collections.defaultdict(list)
    for dist in distributions():
        for pkg in _top_level_declared(dist) or _top_level_inferred(dist):
            pkg_to_dist[pkg].append(dist.metadata["Name"])

    return dict(pkg_to_dist)


def _top_level_declared(dist: Distribution) -> list[str]:
    return (dist.read_text("top_level.txt") or "").split()


def _topmost(name: PackagePath) -> Optional[str]:
    top, *rest = name.parts
    return top if rest else None


def _get_toplevel_name(name: PackagePath) -> str:
    return _topmost(name) or (inspect.getmodulename(name) or str(name))


def _always_iterable(obj: object) -> Iterable[Any]:
    if obj is None:
        return iter(())

    if isinstance(obj, (str, bytes)):
        return iter((obj,))

    try:
        return iter(obj)  # type: ignore[reportUnknownVariableType]
    except TypeError:
        return iter((obj,))


def _top_level_inferred(dist: Distribution) -> Iterable[str]:
    opt_names = set(map(_get_toplevel_name, _always_iterable(dist.files)))

    def importable_name(name: str) -> bool:
        return "." not in name

    return filter(importable_name, opt_names)
