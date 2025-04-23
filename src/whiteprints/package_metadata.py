# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

import importlib
import sys
from collections.abc import Iterable
from functools import cache
from typing import Final, no_type_check


if sys.version_info >= (3, 10):
    from importlib.metadata import PackageMetadata, PackagePath
else:
    from importlib_metadata import PackageMetadata, PackagePath


__all__: Final = [
    "distribution_name",
    "find_license_expression",
    "find_license_files",
    "find_version",
]
"""Public module attributes."""


def _find_license_files(
    *,
    license_paths: Iterable[PackagePath],
    license_files: Iterable[str],
) -> list[PackagePath]:
    """Find the licenses in the wheel defined in the package metadata.

    Args:
        license_paths: list of license paths found in the package wheel.
        license_files: list of licenses found in the wheel metadata.

    Example:
        >>> from importlib import metadata
        >>> from whiteprints.package_metadata import distribution_name
        >>>
        >>> distribution_name = distribution_name()
        >>> licenses = _find_license_files(
        >>>     license_paths=metadata.files(distribution_name) or [],
        >>>     license_files=(
        >>>         metadata.metadata(distribution_name).get_all(
        >>>             "License-File"
        >>>         ) or []
        >>>     )
        >>> )
        >>> len(licenses) > 0
        True

    Returns:
        the list of code licenses used by the present package.
    """
    return [
        license_path
        for license_path in license_paths
        for license_file in license_files
        if license_path.match(license_file)
    ]


@cache
def distribution_name() -> str:
    """Find the present distribution name.

    The distribution name cannot be inferred safely from `__package__ and
    `packages_distribution` as `packages_distribution` might miss editable
    install. Hence it is safer to hard code the distribution name.

    Returns:
        the present package name.
    """
    return "whiteprints"


@cache
def find_version() -> str:
    """Find the package version number.

    Returns:
        The package version.
    """
    return importlib.import_module("importlib.metadata").version(
        distribution_name()
    )


# We ignore type checking here since PackageMetadata is not runtime checkable.
@cache
@no_type_check
def find_metadata() -> PackageMetadata:
    return importlib.import_module("importlib.metadata").metadata(
        distribution_name()
    )


@cache
def find_license_expression() -> str:
    """Find the license expression for the current package.

    Returns:
        the license expression.
    """
    return find_metadata()["License-Expression"]


@cache
def find_license_files() -> list[PackagePath]:
    """Find the license files for the current package.

    Returns:
        A list containing the path to the license(s) of the package code.
    """
    if sys.version_info >= (3, 10):
        files = importlib.import_module("importlib.metadata").files
    else:
        files = importlib.import_module("importlib_metadata").files

    return _find_license_files(
        license_paths=files(distribution_name()) or [],
        license_files=(
            importlib.import_module("importlib.metadata")
            .metadata(distribution_name())
            .get_all("License-File")
            or []
        ),
    )
