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

import sys
from functools import cache
from importlib.metadata import Distribution
from typing import Final, TypedDict

from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString
from whiteprints.redactor import PathRedactor


__all__: Final = [
    "DebugInfo",
    "PackageInfo",
    "gather_distributions",
    "gather_platform_info",
]
"""Public module attributes."""


if sys.version_info >= (3, 13):
    from typing import ReadOnly
else:
    from typing_extensions import ReadOnly


class PackageInfo(TypedDict):
    """Holds current package information."""

    name: ReadOnly[str]
    version: ReadOnly[str]
    origin: ReadOnly[SafeString | None]


class LogsInfo(TypedDict):
    """Holds the logging configuration."""

    USER_LOG_DIR: ReadOnly[SafeString]
    default_configuration: ReadOnly[str | None]


class PythonBuild(TypedDict):
    """Holds the Python interpreter build information."""

    origin: ReadOnly[SafeString]
    date: ReadOnly[SafeString]


class PythonInfo(TypedDict):
    """Holds the Python interpreter information."""

    executable: ReadOnly[SafeString]
    version: ReadOnly[list[str | int]]
    implementation: ReadOnly[str]
    build: ReadOnly[PythonBuild]
    compiler: ReadOnly[SafeString]


class EnvironmentInfo(TypedDict):
    """Holds the environment information."""

    VIRTUAL_ENV: ReadOnly[SafeString | None]
    base_exec_prefix: ReadOnly[SafeString]
    pythonpath: ReadOnly[list[SafeString]]


class PlatformInfo(TypedDict):
    """Holds the platform configuration."""

    os: ReadOnly[dict[str, str | SafeString]]
    python: ReadOnly[PythonInfo]
    environment: ReadOnly[EnvironmentInfo]


class DebugInfo(TypedDict):
    """Holds runtime debug information."""

    platform: ReadOnly[PlatformInfo]
    package: ReadOnly[PackageInfo]


def _find_origin(
    package_name: str | None, path_redactor: PathRedactor
) -> SafeString | None:
    """Find the origin path of a package.

    If the package_name is None, returns None.

    Args:
        package_name: The package name to find the origin from.
        path_redactor: A redactor that hide sensitive information in paths.

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
        or (spec := import_lazy("importlib.util").find_spec(package_name))
        is None
        or spec.origin is None
    ):
        return None

    return import_lazy_project("redaction").Sensitive(
        import_lazy("os").path.dirname(spec.origin),
        path_redactor,
        "spec.origin",
    )


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
            import_lazy("importlib.metadata").packages_distributions().items()
        )
        for distribution in distributions
    }


def _list_site_packages(
    root_distribution: Distribution, path_redactor: PathRedactor
) -> list[PackageInfo]:
    """List the distribution in a site package.

    Args:
        root_distribution: The root distribution to remove from the list.
        path_redactor: A redactor that hide sensitive information in paths.

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
                ),
                path_redactor,
            ),
        )
        for distribution in (import_lazy("importlib.metadata").distributions())
        if (
            distribution.metadata["name"] != root_distribution.metadata["name"]
        )
    ]


def gather_platform_info(virtual_env: SafeString) -> DebugInfo:
    """Gather detailed runtime platform information of the current environment.

    This function collects information about the operating system, the Python
    environment, package versions, and dependencies. It retrieves details such
    as the Python version, platform information, and the version of the
    executing package. Additionally, it includes the Python path and
    information about runtime dependencies, including their names, versions,
    and locations (if available).

    Example:
        >>> gather_platform_info()
        { ... }

    Returns:
        platform information.
    """
    platform = import_lazy("platform")
    redaction = import_lazy_project("redaction")
    path_redactor = import_lazy_project("redactor").PathRedactor()

    buildno, builddate = platform.python_build()
    return DebugInfo(
        platform=PlatformInfo(
            os={
                k: (
                    v
                    if k in {"machine", "system"}
                    else redaction.Secret(v, k.upper(), "platform.uname")
                )
                for k, v in platform.uname()._asdict().items()
                if k != "processor"
            },
            python=PythonInfo(
                executable=redaction.Sensitive(
                    sys.executable,
                    path_redactor,
                    "sys.executable",
                ),
                version=platform.python_version(),
                implementation=platform.python_implementation(),
                build={
                    "origin": redaction.Secret(
                        buildno,
                        "BUILD_ORIGIN",
                        "platform.python_build",
                    ),
                    "date": redaction.Secret(
                        builddate,
                        "BUILD_DATE",
                        "platform.python_build",
                    ),
                },
                compiler=redaction.Secret(
                    platform.python_compiler(), "COMPILER", "platform.python"
                ),
            ),
            environment=EnvironmentInfo(
                VIRTUAL_ENV=virtual_env,
                base_exec_prefix=redaction.Sensitive(
                    sys.base_exec_prefix,
                    path_redactor,
                    "sys.base_exec_prefix",
                ),
                pythonpath=[
                    redaction.Sensitive(
                        path,
                        path_redactor,
                        "sys.path",
                    )
                    for path in sys.path
                ],
            ),
        ),
        package=PackageInfo(
            name=DISTRIBUTION_NAME,
            version=(
                import_lazy("importlib.metadata").distribution(
                    DISTRIBUTION_NAME
                )
            ).version,
            origin=_find_origin(
                _gather_distributions_packages().get(DISTRIBUTION_NAME),
                path_redactor,
            ),
        ),
    )


@cache
def gather_distributions() -> list[PackageInfo]:
    """Gather detailed information about the program's distributons.

    Example:
    .redactor        >>> gather_distributions()
            { ... }

    Returns:
            List of program's distributions.
    """
    path_redactor = import_lazy_project("redactor").PathRedactor()
    return _list_site_packages(
        import_lazy("importlib.metadata").distribution(DISTRIBUTION_NAME),
        path_redactor=path_redactor,
    )
