# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the debug_info module."""

from pathlib import Path

from whiteprints.debug_info import gather_debug_info


class TestGatherDebugInfo:
    """Test that runtime debug info are gathered correctly."""

    @staticmethod
    def test_gather_debug_info_basic() -> None:
        """Test that gather_debug_info returns expected structure."""
        debug_info = gather_debug_info()
        assert isinstance(debug_info, dict)
        assert "platform" in debug_info
        assert "python_version" in debug_info
        assert "package_version" in debug_info
        assert "operating_system" in debug_info
        assert isinstance(debug_info["dependencies"], list)
        assert isinstance(debug_info["pythonpath"], list)
        assert all(isinstance(p, Path) for p in debug_info["pythonpath"])

    @staticmethod
    def test_operating_system_info() -> None:
        """Test that the operating system information is present."""
        debug_info = gather_debug_info()
        assert "operating_system" in debug_info

    @staticmethod
    def test_dependencies_info_structure() -> None:
        """Ensure that dependencies have the expected structure."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            assert "name" in dependency
            assert "version" in dependency
            assert isinstance(dependency["name"], str)
            assert isinstance(dependency["version"], str)
            if "origin" in dependency:
                assert isinstance(dependency["origin"], Path)
