# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

from importlib import metadata
from typing import Final


__all__: Final = ["__license__", "__license_file__", "__version__"]
"""Public module attributes."""

__version__: Final = metadata.version(__package__ or "")
"""The package version number as found by importlib metadata."""

__metadata__: Final = metadata.metadata(__package__ or "")
"""The package metadata."""

__license__: Final = __metadata__["License-Expression"]
"""The package code license as found by importlib metadata."""

__license_file__: Final = [
    license_path
    for license_path in (metadata.files(__package__ or "") or [])
    for license_file in (__metadata__.get_all("License-File") or [])
    if license_path.match(license_file)
]
"""A list containing the path to the license(s) of the package code."""
