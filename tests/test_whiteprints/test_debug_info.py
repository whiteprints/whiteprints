# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the debug_info module."""

import pytest

from whiteprints.debug_info import gather_debug_info


class TestGatherDebugInfo:
    """Test that runtime debug info is gathered correctly."""

    @staticmethod
    def test_gather_debug_info_type() -> None:
        """Test that gather_debug_info returns a dictionary."""
        debug_info = gather_debug_info()
        assert isinstance(debug_info, dict), (
            f"Expected debug_info to be a dict, "
            f"but got {type(debug_info).__name__}"
        )

    @staticmethod
    @pytest.mark.parametrize(
        "key",
        [
            "platform",
            "package",
            "logs",
        ],
    )
    def test_gather_debug_info_keys(key: str) -> None:
        """Test that gather_debug_info contains required keys."""
        debug_info = gather_debug_info()
        assert key in debug_info, f"'{key}' key missing in debug_info."
