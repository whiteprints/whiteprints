# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Gather and organize runtime information for the current Python environment.

This module provides functionality to collect comprehensive debug details such
as operating system specifics, Python interpreter information, package
versioning, and dependency data. It is designed to facilitate troubleshooting
by generating a structured snapshot of the environment in which the code is
running.

The collected data includes:
    - OS distribution details (e.g., name, version).
    - Python version and platform information.
    - Package versions, including the version of this module.
    - A list of Python paths where modules are searched.
    - Detailed information about runtime dependencies, including their versions
      and locations when available.

This is useful for debugging issues related to dependency resolution,
environment configuration across different systems.
"""

import platform
import re
import sys
from functools import cache
from importlib import metadata
from importlib.metadata import Distribution
from importlib.util import find_spec
from pathlib import Path
from typing import Final, TypedDict

from distro import distro
from distro.distro import InfoDict

from whiteprints import __version__


__all__: Final = ["DebugInfo", "PackageInfo", "gather_debug_info"]


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
    python_executable: Path
    package_version: str
    pythonpath: list[Path]
    dependencies: list[PackageInfo]


class _DistributionPackage(TypedDict):
    """Holds a distribution with its corresponding package name."""

    distribution: Distribution
    package_name: str


def _add_spec(package_info: PackageInfo, *, package_name: str) -> None:
    """Add the origin path of a package to its information if available.

    Uses `find_spec` to locate the module specification for the given package
    name. If a valid origin (file path) is found, it adds this path to the
    `origin` field of the `package_info` dictionary.

    Args:
        package_info: A dictionary holding package information, including
            its name and version.
        package_name: The name of the package to locate and add the origin
            path for.

    Example:
        >>> package_info = {"name": "example", "version": "1.0"}
        >>> _add_spec(package_info, package_name="os")
        >>> "origin" in package_info
        True
        >>> isinstance(package_info["origin"], Path)
        True
        >>> package_info = {"name": "nonexistent-package", "version": "1.0"}
        >>> _add_spec(package_info, package_name="some_nonexistent_package")
        >>> "origin" not in package_info
        True
    """
    spec = find_spec(package_name)
    if spec is not None and spec.origin is not None:
        package_info["origin"] = Path(spec.origin)


def _package_info_from_name(
    distribution_package: _DistributionPackage,
) -> PackageInfo:
    """Construct a package information dictionary for a given distribution.

    Args:
        distribution_package: The metadata distribution object representing the
            package and name of the package to find, which may differ from the
            distribution name.

    Returns:
        A dictionary containing:
            - name: The name of the package as provided by the distribution.
            - version: The version of the package.
            - origin: The file path where the package is installed, if
              available.
    """
    distribution = distribution_package["distribution"]
    package_info = PackageInfo(
        name=distribution.metadata["Name"],
        version=distribution.version,
    )
    _add_spec(
        package_info,
        package_name=distribution_package["package_name"],
    )

    return package_info


@cache
def _gather_required_packages() -> list[str]:
    """Gather the list of required packages for the current module.

    Parses the dependencies of the current module to identify required packages
    and normalizes their names by replacing hyphens with underscores.

    Returns:
        A list of normalized package names extracted from the requirements.
    """
    package_name_regex = re.compile("==|===|~=|!=|>=|>|<=|<")
    return [
        package_name_regex.split(package, maxsplit=1)[0].replace("-", "_")
        for package in (
            metadata.distribution(__package__ or "").requires or []
        )
    ]


@cache
def _gather_distribution_packages() -> dict[str, str]:
    """Map installed distributions to their corresponding package names.

    Retrieves a mapping of distribution names to the package names that
    they provide, with distribution names normalized by replacing hyphens
    with underscores.

    Returns:
        A dictionary where keys are normalized distribution names and values
        are package names.
    """
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
    """Find distribution objects for the required packages.

    Uses a list of required package names and a mapping of distribution
    packages to identify the corresponding distribution metadata objects.

    Args:
        required: A list of package names that are required.
        distributions_packages: A dictionary mapping normalized distribution
            names to their corresponding package names.

    Returns:
        A list of dictionaries where each entry contains:
            - distribution: The metadata distribution object for the package.
            - package_name: The name of the package that corresponds to the
              distribution.
    """
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


@cache
def gather_debug_info() -> DebugInfo:
    """Gather detailed runtime debug information of the current environment.

    This function collects information about the operating system, the Python
    environment, package versions, and dependencies. It retrieves details such
    as the OS distribution, Python version, platform information, and the
    version of the executing package. Additionally, it includes the Python path
    and information about runtime dependencies, including their names,
    versions, and locations (if available).

    Returns:
        DebugInfo: A dictionary containing:
            - operating_system: Details about the current OS
              distribution including name, version, and ID.
            - platform: A string representing the underlying platform,
              e.g., 'Linux-5.15.0-76-generic-x86_64-with-glibc2.31'.
            - python_version: The full version string of the Python interpreter
              being used, e.g., '3.12.0'.
            - package_version: The version of the `whiteprints` package.
            - pythonpath: A list of paths where Python searches for
              modules.
            - dependencies: A list of dictionaries where each
              entry represents a runtime dependency with its name, version,
              and, if available, the path to the module's origin file.
    """
    required_distribution = _find_required_distributions(
        required=_gather_required_packages(),
        distributions_packages=_gather_distribution_packages(),
    )

    return DebugInfo(
        operating_system=distro.info(),
        platform=platform.platform(),
        python_executable=Path(sys.executable),
        python_version=sys.version,
        package_version=__version__,
        pythonpath=list(map(Path, sys.path)),
        dependencies=[
            _package_info_from_name(distribution_package)
            for distribution_package in required_distribution
        ],
    )
