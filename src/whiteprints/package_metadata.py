# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

import importlib
import sys
from collections.abc import Iterable
from functools import cache
from typing import Final

from whiteprints.exception import NotAPackageError


if sys.version_info >= (3, 10):
    from importlib.metadata import PackagePath
else:
    from importlib_metadata import PackagePath


__all__: Final = [
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
        >>>
        >>> licenses = _find_license_files(
        >>>     license_paths=metadata.files(__package__) or [],
        >>>     license_files=(
        >>>         metadata.metadata(__package__).get_all("License-File")
        >>>         or []
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
def _find_present_package() -> str:
    """Find the present package name.

    Raises:
        NotAPackageError: the current project is not a package.

    Returns:
        the present package name.
    """
    package_name = __package__
    if package_name is None:
        raise NotAPackageError

    return package_name


@cache
def find_version() -> str:
    """Find the package version number.

    Returns:
        The package version.
    """
    return importlib.import_module("importlib.metadata").version(
        _find_present_package()
    )


@cache
def find_license_expression() -> str:
    """Find the license expression for the current package.

    Returns:
        the license expression.
    """
    return importlib.import_module("importlib.metadata").metadata(
        _find_present_package()
    )["License-Expression"]


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
        license_paths=files(_find_present_package()) or [],
        license_files=(
            importlib.import_module("importlib.metadata")
            .metadata(_find_present_package())
            .get_all("License-File")
            or []
        ),
    )
