# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

import importlib
from collections.abc import Iterable
from functools import cache
from importlib.metadata import PackageMetadata, PackagePath
from typing import Final, no_type_check


__all__: Final = [
    "distribution_name",
    "find_license_expression",
    "find_license_files",
    "find_version",
]
"""Public module attributes."""


def _is_license(file: str) -> bool:
    """Check if a license file path is valid.

    Args:
        file: The file path to check.

    Returns:
        True if the file path is valid, False otherwise
    """
    return file.startswith("LICENSES/") and file.endswith(r".txt")


def _match_license_path_and_filename(
    license_path: PackagePath,
    license_file_set: set[str],
) -> bool:
    """Find the licenses in the wheel defined in the package metadata.

    Args:
        license_path: a icense path found in the package wheel.
        license_file_set: set of licenses found in the wheel metadata.

    Returns:
        True if the license path and filename matches, False otherwise.
    """
    return any(
        license_path.stem in license_file for license_file in license_file_set
    )


def _find_license_files(
    *,
    license_paths: Iterable[PackagePath],
    license_files: Iterable[str],
) -> set[PackagePath]:
    """Find the licenses in the wheel defined in the package metadata.

    Args:
        license_paths: license paths found in the package wheel.
        license_files: licenses found in the wheel metadata.

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
    return {
        license_path
        for license_path in license_paths
        if _match_license_path_and_filename(
            license_path, {file for file in license_files if _is_license(file)}
        )
    }


@cache
def distribution_name() -> str:
    """Find the present distribution name.

    This function exists because the distribution name cannot be inferred
    safely from `__package__ and `packages_distribution` as
    `packages_distribution` might miss editable install. Hence it is safer to
    hard code the distribution name.

    The result is cached.

    Example:
        >>> distribution_name()
        whiteprints

    Returns:
        the present package name.
    """
    return "whiteprints"


@cache
def find_version() -> str:
    """Find present the package version number.

    Example:
        >>> find_version()
        ...

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
    """Find the present package metadata.

    The result is cached.

    Example:
        >>> find_metadata()
        ...

    Returns:
        The package metadata.
    """
    return importlib.import_module("importlib.metadata").metadata(
        distribution_name()
    )


@cache
def find_license_expression() -> str:
    """Find the license expression for the current package.

    Example:
        >>> assert isinstance(find_license_expression(), str)

    Returns:
        The license expression.
    """
    return find_metadata()["License-Expression"]


@cache
def find_license_files() -> set[PackagePath]:
    """Find the license files for the current package.

    Example:
        >>> find_license_files()
        {...}

    Returns:
        A list containing the path to the license(s) of the package code.
    """
    return _find_license_files(
        license_paths=importlib.import_module("importlib.metadata").files(
            distribution_name()
        )
        or [],
        license_files=(find_metadata().get_all("License-File") or []),
    )
