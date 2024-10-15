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


class DebugInfo(TypedDict):
    """Holds runtime debug information."""

    operating_system: InfoDict
    platform: str
    python_version: str
    package_version: str
    pythonpath: list[Path]
    dependencies: list[PackageInfo]


class _DistributionPackage(TypedDict):
    """Holds a distribution with its corresponding package name."""

    distribution: Distribution
    package_name: str


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


def _gather_required_packages() -> list[str]:
    package_name_regex = re.compile("==|===|~=|!=|>=|>|<=|<")
    return [
        package_name_regex.split(package, maxsplit=1)[0].replace("-", "_")
        for package in (
            metadata.distribution(__package__ or "").requires or []
        )
    ]


def _gather_distribution_packages() -> dict[str, str]:
    return {
        str(distribution).replace("-", "_"): str(package)
        for package, distributions in packages_distributions().items()
        for distribution in distributions
    }


def _find_required_distributions(
    *,
    required: list[str],
    distributions_packages: dict[str, str],
) -> list[_DistributionPackage]:
    required_distribution: list[_DistributionPackage] = []
    for distribution in required:
        package_name = distributions_packages.get(distribution)
        if package_name is not None:
            required_distribution.append(
                _DistributionPackage(
                    distribution=metadata.distribution(distribution),
                    package_name=package_name,
                )
            )

    return required_distribution


def gather_debug_info() -> DebugInfo:
    """Gather runtime debug information.

    Args:
        tracked_dependencies: the dependencies from which to track debug
            information.

    Returns:
        the global debug information.
    """
    required_distribution = _find_required_distributions(
        required=_gather_required_packages(),
        distributions_packages=_gather_distribution_packages(),
    )

    return DebugInfo(
        operating_system=distro.info(),
        platform=platform.platform(),
        python_version=sys.version,
        package_version=__version__,
        pythonpath=list(map(Path, sys.path)),
        dependencies=[
            _package_info_from_name(**distribution_package)
            for distribution_package in required_distribution
        ],
    )
