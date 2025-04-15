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

import importlib
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import metadata
from importlib.util import find_spec
from pathlib import Path
from re import Pattern
from typing import Final, Optional, TypedDict, Union


if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if sys.version_info >= (3, 10):
    from importlib.metadata import (
        Distribution,
        PathDistribution,
        packages_distributions,
    )
else:
    from importlib_metadata import (
        Distribution,
        PathDistribution,
        packages_distributions,
    )


__all__: Final = ["DebugInfo", "gather_debug_info"]


@dataclass(frozen=True)
class _DistributionPackage:
    """Holds a distribution with its corresponding package name."""

    distribution: Union[Distribution, PathDistribution]
    package_name: Optional[str]


class PackageInfo(TypedDict):
    """Holds runtime dependency information."""

    name: str
    version: str
    origin: Optional[str]
    dependencies: Optional[list[Self]]


class LogsInfo(TypedDict):
    """Holds the logging configuration."""

    USER_LOG_DIR: str
    default_configuration: Optional[str]


class PythonInfo(TypedDict):
    """Holds the Python interpreter information."""

    executable: str
    version: list[Union[str, int]]
    implementation: str
    build: str
    compiler: str


class EnvironmentInfo(TypedDict):
    """Holds the environment information."""

    VIRTUAL_ENV: Optional[str]
    base_exec_prefix: str
    pythonpath: list[str]


class PlatformInfo(TypedDict):
    """Holds the platform configuration."""

    name: str
    python: PythonInfo
    environment: EnvironmentInfo


class DebugInfo(TypedDict):
    """Holds runtime debug information."""

    platform: PlatformInfo
    package: Optional[PackageInfo]
    logs: Optional[LogsInfo]


@cache
def _gather_packages_distributions() -> Mapping[str, list[str]]:
    """Cache wrapper for packages_distributions function.

    Returns:
        a package distributions mapping.
    """
    return packages_distributions()


@cache
def _gather_distributions_packages() -> dict[str, str]:
    """Map installed distributions to their corresponding package names.

    Retrieves a mapping of distribution names to the package names that
    they provide, with distribution names normalized by replacing hyphens
    with underscores.

    Returns:
        A dictionary where keys are normalized distribution names and values
        are package names.
    """
    return {
        str(distribution).lower().replace("-", "_"): str(package)
        for package, distributions in _gather_packages_distributions().items()
        for distribution in distributions
    }


@cache
def _package_info_from_name(
    distribution_package: _DistributionPackage,
    *,
    dependencies: bool = True,
    ancestors_distributions: frozenset[str] = frozenset[str](),
) -> PackageInfo:
    """Construct a package information dictionary for a given distribution.

    Args:
        distribution_package: The metadata distribution object representing the
            package and name of the package to find, which may differ from the
            distribution name.
        dependencies: add dependency list to each distribution.
        ancestors_distributions: set of parents distributions.

    Returns:
        A dictionary containing:
            - name: The name of the package as provided by the distribution.
            - version: The version of the package.
            - origin: The file path where the package is installed, if
              available.
    """
    distribution = distribution_package.distribution
    package_name = distribution_package.package_name

    spec = None if package_name is None else find_spec(package_name)
    distribution_name = distribution.metadata["name"]
    if distribution_name in ancestors_distributions:
        return PackageInfo(
            name=distribution_name,
            version=distribution.version,
            origin=(
                str(Path(spec.origin).parent)
                if spec is not None and spec.origin is not None
                else None
            ),
            dependencies=None,
        )

    return PackageInfo(
        name=distribution_name,
        version=distribution.version,
        origin=(
            str(Path(spec.origin).parent)
            if spec is not None and spec.origin is not None
            else None
        ),
        dependencies=[
            _package_info_from_name(
                dependency_distribution_package,
                ancestors_distributions=frozenset[str].union(
                    ancestors_distributions,
                    {distribution_name},
                ),
            )
            for dependency_distribution_package in (
                _find_requested_distributions
            )(
                requested=_gather_requested_packages(distribution_name),
                distributions_packages=_gather_distributions_packages(),
            )
        ]
        if dependencies
        else None,
    )


@cache
def _package_name_regex() -> Pattern[str]:
    """A regex to split package name from its version.

    Returns:
        the regex.
    """
    return importlib.import_module("re").compile(
        r" |\(|==|===|~=|!=|>=|>|<=|<"
    )


@cache
def _gather_requested_packages(module: str) -> list[str]:
    """Gather the list of requested packages for a given current module.

    Parses the dependencies of the current module to identify requested
    packages and normalizes their names by replacing hyphens with underscores.

    Returns:
        A list of normalized package names extracted from the requirements.
    """
    return [
        _package_name_regex()
        .split(
            package.split(";", maxsplit=1)[0],  # remove comments
            maxsplit=1,
        )[0]
        .lower()
        .replace("-", "_")
        for package in (metadata.distribution(module).requires or [])
    ]


def _find_requested_distributions(
    *,
    requested: list[str],
    distributions_packages: dict[str, str],
) -> list[_DistributionPackage]:
    """Find distribution objects for the requested packages.

    Uses a list of requested package names and a mapping of distribution
    packages to identify the corresponding distribution metadata objects.

    Args:
        requested: A list of package names that are requested.
        distributions_packages: A dictionary mapping normalized distribution
            names to their corresponding package names.

    Returns:
        A list of dictionaries where each entry contains:
            - distribution: The metadata distribution object for the package.
            - package_name: The name of the package that corresponds to the
              distribution.
    """
    requested_distribution: list[_DistributionPackage] = []
    for distribution in requested:
        package_name = distributions_packages.get(distribution)
        if package_name is not None:
            requested_distribution.append(
                _DistributionPackage(
                    distribution=metadata.distribution(distribution),
                    package_name=package_name,
                )
            )

    return requested_distribution


@cache
def gather_debug_info(*, dependencies: bool = True) -> DebugInfo:
    """Gather detailed runtime debug information of the current environment.

    This function collects information about the operating system, the Python
    environment, package versions, and dependencies. It retrieves details such
    as the OS distribution, Python version, platform information, and the
    version of the executing package. Additionally, it includes the Python path
    and information about runtime dependencies, including their names,
    versions, and locations (if available).

    Example:
        >>> gather_debug_info()
        { ... }

    Returns:
        DebugInfo: useful debugging information.
    """
    logs = importlib.import_module(
        "whiteprints.cli.logs",
        __package__,
    )
    log_config = logs.user_log_config()
    distribution_name = importlib.import_module(
        "whiteprints.package_metadata",
        __package__,
    ).distribution_name()

    platform = importlib.import_module("platform")

    return DebugInfo(
        platform=PlatformInfo(
            name=platform.uname(),
            python=PythonInfo(
                executable=str(Path(sys.executable)),
                version=platform.python_version(),
                implementation=platform.python_implementation(),
                build=platform.python_build(),
                compiler=platform.python_compiler(),
            ),
            environment=EnvironmentInfo(
                VIRTUAL_ENV=os.environ.get("VIRTUAL_ENV"),
                base_exec_prefix=sys.base_exec_prefix,
                pythonpath=list(map(str, map(Path, sys.path))),
            ),
        ),
        package=_package_info_from_name(
            _DistributionPackage(
                distribution=metadata.distribution(distribution_name),
                package_name=__package__,
            ),
            dependencies=dependencies,
        ),
        logs=LogsInfo(
            USER_LOG_DIR=str(logs.user_log_dir()),
            default_configuration=(
                None if log_config is None else str(log_config)
            ),
        ),
    )
