# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's version number."""

from importlib import metadata
from typing import Final


__all__: Final = ["__license__", "__license_file__", "__version__"]
"""Public module attributes."""

__version__: Final = metadata.version(__package__ or "")
"""The package version number as found by importlib metadata."""

__license__: Final = metadata.metadata(__package__ or "")["License-Expression"]
"""The package code license as found by importlib metadata."""

__license_file__: Final = [
    license_path
    for license_path in metadata.files(__package__ or "") or ()
    if license_path.match("LICENSES/*.txt")
]
"""The package code license file as found by importlib metadata."""
