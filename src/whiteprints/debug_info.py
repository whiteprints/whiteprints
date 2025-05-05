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

Note: we cannot do the .dist-info hypothesis as in metadata.py since we
do not know how the dependencies were installed (they could use deprecated or
legacy packaging). Hence we use the slower but more robust importlib.metadata
"""

import importlib
import sys
from functools import cache
from importlib.metadata import Distribution
from typing import Final, TypedDict


__all__: Final = ["DebugInfo", "gather_debug_info"]


if sys.version_info >= (3, 13):
    from typing import ReadOnly
else:
    from typing_extensions import ReadOnly


class PackageInfo(TypedDict):
    """Holds current package information."""

    name: ReadOnly[tuple[str, str, str, str, str]]
    version: ReadOnly[str]
    origin: ReadOnly[str | None]


class LogsInfo(TypedDict):
    """Holds the logging configuration."""

    USER_LOG_DIR: ReadOnly[str]
    default_configuration: ReadOnly[str | None]


class PythonInfo(TypedDict):
    """Holds the Python interpreter information."""

    executable: ReadOnly[str]
    version: ReadOnly[list[str | int]]
    implementation: ReadOnly[str]
    build: ReadOnly[str]
    compiler: ReadOnly[str]


class EnvironmentInfo(TypedDict):
    """Holds the environment information."""

    VIRTUAL_ENV: ReadOnly[str | None]
    base_exec_prefix: ReadOnly[str]
    pythonpath: ReadOnly[list[str]]


class PlatformInfo(TypedDict):
    """Holds the platform configuration."""

    name: ReadOnly[str]
    python: ReadOnly[PythonInfo]
    environment: ReadOnly[EnvironmentInfo]


class DebugInfo(TypedDict):
    """Holds runtime debug information."""

    platform: ReadOnly[PlatformInfo]
    package: ReadOnly[PackageInfo]
    site_packages: ReadOnly[list[PackageInfo] | None]
    logs: ReadOnly[LogsInfo | None]


def _find_origin(package_name: str | None) -> str | None:
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
        or (
            spec := importlib.import_module("importlib.util").find_spec(
                package_name
            )
        )
        is None
        or spec.origin is None
    ):
        return None

    return str(importlib.import_module("os").path.dirname(spec.origin))


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
        for package, distributions in (
            importlib.import_module("importlib.metadata")
            .packages_distributions()
            .items()
        )
        for distribution in distributions
    }


def _list_site_packages(root_distribution: Distribution) -> list[PackageInfo]:
    """List the distribution in a site package.

    Args:
        root_distribution: the root distribution to remove from the list.

    Returns:
        A list of distributions present in the site package.
    """
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
        for distribution in (
            importlib.import_module("importlib.metadata").distributions()
        )
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
    return DebugInfo(
        platform=PlatformInfo(
            name=(platform := importlib.import_module("platform")).uname(),
            python=PythonInfo(
                executable=sys.executable,
                version=platform.python_version(),
                implementation=platform.python_implementation(),
                build=platform.python_build(),
                compiler=platform.python_compiler(),
            ),
            environment=EnvironmentInfo(
                VIRTUAL_ENV=importlib.import_module("os").environ.get(
                    "VIRTUAL_ENV"
                ),
                base_exec_prefix=sys.base_exec_prefix,
                pythonpath=sys.path,
            ),
        ),
        package=PackageInfo(
            name=(
                distribution_name := importlib.import_module(
                    "whiteprints.metadata"
                ).DISTRIBUTION_NAME
            ),
            version=(
                root_distribution := importlib.import_module(
                    "importlib.metadata"
                ).distribution(distribution_name)
            ).version,
            origin=_find_origin(
                _gather_distributions_packages().get(distribution_name)
            ),
        ),
        site_packages=(
            _list_site_packages(root_distribution) if site_packages else None
        ),
        logs=LogsInfo(
            USER_LOG_DIR=str(
                (
                    logs := importlib.import_module(
                        "whiteprints.cli.logs",
                    )
                ).user_log_dir()
            ),
            default_configuration=(
                None
                if (log_config := logs.user_log_config()) is None
                else str(log_config)
            ),
        ),
    )
