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
        assert isinstance(debug_info, dict), (
            "Expected debug_info to be a dict, "
            f"but got {type(debug_info).__name__}"
        )
        assert (
            "platform" in debug_info
        ), "'platform' key missing in debug_info."
        assert (
            "python_version" in debug_info
        ), "'python_version' key missing in debug_info."
        assert (
            "package_version" in debug_info
        ), "'package_version' key missing in debug_info."
        assert (
            "operating_system" in debug_info
        ), "'operating_system' key missing in debug_info."
        assert isinstance(debug_info["dependencies"], list), (
            "'dependencies' should be a list, "
            f"but got {type(debug_info['dependencies']).__name__}"
        )
        assert isinstance(debug_info["pythonpath"], list), (
            "'pythonpath' should be a list, "
            f"but got {type(debug_info['pythonpath']).__name__}"
        )
        assert all(
            isinstance(p, Path) for p in debug_info["pythonpath"]
        ), "All elements in 'pythonpath' should be Path instances."

    @staticmethod
    def test_operating_system_info() -> None:
        """Test that the operating system information is present."""
        debug_info = gather_debug_info()
        assert (
            "operating_system" in debug_info
        ), "'operating_system' key missing in debug_info."

    @staticmethod
    def test_dependencies_info_structure() -> None:
        """Ensure that dependencies have the expected structure."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            assert "name" in dependency, "Dependency missing 'name' field."
            assert (
                "version" in dependency
            ), f"Dependency '{dependency['name']}' missing 'version' field."
            assert isinstance(dependency["name"], str), (
                "'name' should be a string in dependency, "
                f"but got {type(dependency['name']).__name__}."
            )
            assert isinstance(dependency["version"], str), (
                "'version' should be a string in dependency"
                f" '{dependency['name']}',"
                f" but got {type(dependency['version']).__name__}."
            )
            if "origin" in dependency:
                assert isinstance(dependency["origin"], Path), (
                    "'origin' should be a Path in dependency"
                    f" '{dependency['name']}', but got"
                    f" {type(dependency['origin']).__name__}."
                )
