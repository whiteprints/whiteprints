# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the loc module."""

from pathlib import Path

from whiteprints import loc


class TestLocalVariables:
    """Test the localization variables."""

    @staticmethod
    def test_locale_directory_is_a_valid_path() -> None:
        """Test whether the LOCALE_DIRECTORY is a valid Path."""
        assert isinstance(
            loc.LOCALE_DIRECTORY, Path
        ), "LOCALE_DIRECTORY is not an instance of `Path`"

    @staticmethod
    def test_translation_functions_are_available() -> None:
        """Test whether the translation functions exists.

        The translation functions are `TRANSLATION` and `_`.
        """
        assert hasattr(
            loc, "TRANSLATION"
        ), "Translation function `TRANSLATION` not found."
        assert hasattr(loc, "_"), "Translation function `_` not found."
