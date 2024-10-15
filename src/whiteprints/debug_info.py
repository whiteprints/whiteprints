# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Gather debug information."""

from __future__ import annotations

import platform
import re
import sys
from importlib import metadata
from importlib.metadata import Distribution
from importlib.util import find_spec
from pathlib import Path
from typing import TypedDict

from distro import distro
from distro.distro import InfoDict

from whiteprints import __version__


if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

if sys.version_info < (3, 10):
    from importlib_metadata import packages_distributions
else:
    from importlib.metadata import packages_distributions


class PackageInfo(TypedDict):
    """Holds runtime dependency information."""

    name: str
    version: str
    origin: NotRequired[Path]


def _package_info_from_name(
    distribution: Distribution,
    *,
    package_name: str,
) -> PackageInfo:
    package_info = PackageInfo(
        name=distribution.name,
        version=distribution.version,
    )
    spec = find_spec(package_name)
    if spec is not None and spec.origin is not None:
        package_info["origin"] = Path(spec.origin)

    return package_info


class DebugInfo(TypedDict):
    """Holds runtime debug information."""

    operating_system: InfoDict
    platform: str
    python_version: str
    package_version: str
    pythonpath: list[Path]
    dependencies: list[PackageInfo]


def gather_debug_info() -> DebugInfo:
    """Gather runtime debug information.

    Args:
        tracked_dependencies: the dependencies from which to track debug
            information.

    Returns:
        the global debug information.
    """
    distributions_packages = {
        str(distribution).replace("-", "_"): str(package)
        for package, distributions in packages_distributions().items()
        for distribution in distributions
    }
    package_name_regex = re.compile("==|===|~=|!=|>=|>|<=|<")
    required = [
        package_name_regex.split(package, maxsplit=1)[0].replace("-", "_")
        for package in (
            metadata.distribution(__package__ or "").requires or []
        )
    ]
    required_distribution: list[tuple[Distribution, str]] = []
    for distribution in required:
        package = distributions_packages.get(distribution)
        if package is not None:
            required_distribution.append((
                metadata.distribution(distribution),
                package,
            ))

    return DebugInfo(
        operating_system=distro.info(),
        platform=platform.platform(),
        python_version=sys.version,
        package_version=__version__,
        pythonpath=[Path(path) for path in sys.path],
        dependencies=[
            _package_info_from_name(distribution, package_name=package_name)
            for distribution, package_name in required_distribution
        ],
    )
