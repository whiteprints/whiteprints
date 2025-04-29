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
from functools import cache
from importlib.metadata import (
    Distribution,
    distribution,
    distributions,
    packages_distributions,
)
from importlib.util import find_spec
from pathlib import Path
from typing import Final, Optional, TypedDict, Union


__all__: Final = ["DebugInfo", "gather_debug_info"]


class PackageInfo(TypedDict):
    """Holds current package information."""

    name: str
    version: str
    origin: Optional[str]


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
    package: PackageInfo
    site_packages: Optional[list[PackageInfo]]
    logs: Optional[LogsInfo]


def _find_origin(package_name: Optional[str]) -> Optional[str]:
    """Find the origin path of a package.

    If the package_name is None, returns None.

    Example:
        >>> _find_origin(None)
        >>> None
        >>> _find_origin(__package__)
        ...

    Returns:
        The path to the package origin. None if no path is found or the
        package_name is None.
    """
    if (
        package_name is None
        or (spec := find_spec(package_name)) is None
        or spec.origin is None
    ):
        return None

    return str(Path(spec.origin).parent)


@cache
def _gather_distributions_packages() -> dict[str, str]:
    """Map installed distributions to their corresponding package names.

    Retrieves a mapping of distribution names to the package names that
    they provide, with distribution names normalized by replacing hyphens
    with underscores.

    Example:
        >>> _gather_distributions_packages()
        { ... }

    Returns:
        A dictionary where keys are normalized distribution names and values
        are package names.
    """
    return {
        str(distribution): str(package)
        for package, distributions in packages_distributions().items()
        for distribution in distributions
    }


def _list_site_packages(root_distribution: Distribution) -> list[PackageInfo]:
    return [
        PackageInfo(
            name=distribution.metadata["name"],
            version=distribution.version,
            origin=_find_origin(
                _gather_distributions_packages().get(
                    distribution.metadata["name"]
                )
            ),
        )
        for distribution in distributions()
        if (
            distribution.metadata["name"] != root_distribution.metadata["name"]
        )
    ]


@cache
def gather_debug_info(*, site_packages: bool = True) -> DebugInfo:
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
    )
    log_config = logs.user_log_config()
    platform = importlib.import_module("platform")

    distribution_name = importlib.import_module(
        "whiteprints.package_metadata"
    ).distribution_name()

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
        package=PackageInfo(
            name=distribution_name,
            version=(
                root_distribution := distribution(distribution_name)
            ).version,
            origin=_find_origin(
                _gather_distributions_packages().get(distribution_name)
            ),
        ),
        site_packages=(
            _list_site_packages(root_distribution) if site_packages else None
        ),
        logs=LogsInfo(
            USER_LOG_DIR=str(logs.user_log_dir()),
            default_configuration=(
                None if log_config is None else str(log_config)
            ),
        ),
    )
