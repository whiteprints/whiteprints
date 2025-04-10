# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

import sys
from importlib import metadata
from typing import Any, Final

from whiteprints.exception import NoLicenseFoundError


if sys.version_info >= (3, 10):
    from importlib.metadata import PackagePath
else:
    from importlib_metadata import PackagePath

__all__: Final = [
    "__license__",
    "__license_file__",
    "__metadata__",
    "__version__",
]
"""Public module attributes."""


def _find_license_files(
    *,
    license_paths: list[PackagePath],
    license_files: list[str],
) -> list[PackagePath]:
    """Find the licenses in the wheel defined in the package metadata.

    Args:
        license_paths: list of license paths found in the package wheel.
        license_files: list of licenses found in the wheel metadata.

    Example:
        >>> from importlib import metadata
        >>> licenses = _find_license_files(
        >>>     license_paths=metadata.files(__package__ or "") or [],
        >>>     license_files=__metadata__.get_all("License-File") or [],
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


def _check_license_found(licenses_found: list[Any]) -> None:
    if not len(licenses_found):
        raise NoLicenseFoundError


__version__: Final = metadata.version(__package__ or "")
"""The package version number as found by importlib metadata."""

__metadata__: Final = metadata.metadata(__package__ or "")
"""The package metadata."""

__license__: Final = __metadata__["License-Expression"]
"""The package code license as found by importlib metadata."""

__license_file__: Final = _find_license_files(
    license_paths=metadata.files(__package__ or "") or [],
    license_files=__metadata__.get_all("License-File") or [],
)
"""A list containing the path to the license(s) of the package code."""

_check_license_found(__license_file__)
