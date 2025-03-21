# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the exception module."""

import re
from typing import Final

from hypothesis import given
from hypothesis import strategies as st

from whiteprints.cli import app_metadata


SLUG_REGEX: Final = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


@given(st.from_regex(SLUG_REGEX))
def test_is_valid_slug(slug: str) -> None:
    """Check if the slug is valid."""
    assert app_metadata.is_valid_slug(slug) == bool(
        re.fullmatch(SLUG_REGEX, slug)
    ), f"A valid slug should match the regular expression '{SLUG_REGEX}'."
