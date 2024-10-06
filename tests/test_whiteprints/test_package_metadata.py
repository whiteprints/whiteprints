# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the package_metadata module."""

import re

from whiteprints import package_metadata


VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
              [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""
"""PyPA version specifier.

See: https://packaging.python.org/en/latest/specifications/version-specifiers/
"""


class TestVersion:
    """Test the version metadata."""

    @staticmethod
    def is_canonical(*, version_number: str) -> bool:
        """Determine if version number is well formed.

        Version numbers must respect PEP440

        Returns:
            True if the version number respect PEP440, False otherwise.
        """
        pypa_version = re.compile(
            r"^\s*" + VERSION_PATTERN + r"\s*$",
            re.VERBOSE | re.IGNORECASE,
        )
        return re.match(pypa_version, version_number) is not None

    @staticmethod
    def test___version___respects_pep_440() -> None:
        """Test the version number is well formed.

        Version numbers must respect PEP440
        """
        version_number = package_metadata.__version__
        assert TestVersion.is_canonical(
            version_number=version_number,
        ), f"The version number {version_number} does not respect PEP440."


class TestLicense:
    """Test the license metadata."""

    @staticmethod
    def test___license__() -> None:
        """Test if a license metadata exists."""
        assert package_metadata.__license__, "No license metadata found."

    @staticmethod
    def test___license_file__() -> None:
        """Test if the license files are found."""
        assert package_metadata.__license_file__, "No license file found."
