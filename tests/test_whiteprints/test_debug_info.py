# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Test the debug_info module."""

from pathlib import Path

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
            "python_version",
            "package_version",
            "operating_system",
        ],
    )
    def test_gather_debug_info_keys(key: str) -> None:
        """Test that gather_debug_info contains required keys."""
        debug_info = gather_debug_info()
        assert key in debug_info, f"'{key}' key missing in debug_info."

    @staticmethod
    def test_dependencies_is_list() -> None:
        """Test that 'dependencies' is a list in debug_info."""
        debug_info = gather_debug_info()
        assert isinstance(debug_info["dependencies"], list), (
            "'dependencies' should be a list, "
            f"but got {type(debug_info['dependencies']).__name__}"
        )

    @staticmethod
    def test_pythonpath_is_list() -> None:
        """Test that 'pythonpath' is a list in debug_info."""
        debug_info = gather_debug_info()
        assert isinstance(debug_info["pythonpath"], list), (
            "'pythonpath' should be a list, "
            f"but got {type(debug_info['pythonpath']).__name__}"
        )

    @staticmethod
    def test_pythonpath_elements_are_paths() -> None:
        """Test that all elements in 'pythonpath' are Path instances."""
        debug_info = gather_debug_info()
        assert all(isinstance(p, Path) for p in debug_info["pythonpath"]), (
            "All elements in 'pythonpath' should be Path instances."
        )

    @staticmethod
    def test_operating_system_info_present() -> None:
        """Test that 'operating_system' information is present."""
        debug_info = gather_debug_info()
        assert "operating_system" in debug_info, (
            "'operating_system' key missing in debug_info."
        )

    @staticmethod
    @pytest.mark.parametrize("field", ["name", "version"])
    def test_dependencies_have_required_fields(field: str) -> None:
        """Test that each dependency contains required fields."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            assert field in dependency, f"Dependency missing '{field}' field."

    @staticmethod
    def test_dependency_name_is_str() -> None:
        """Test that 'name' is a string in each dependency."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            assert isinstance(dependency["name"], str), (
                "'name' should be a string in dependency, "
                f"but got {type(dependency['name']).__name__}."
            )

    @staticmethod
    def test_dependency_version_is_str() -> None:
        """Test that 'version' is a string in each dependency."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            assert isinstance(dependency["version"], str), (
                "'version' should be a string in dependency, "
                f"but got {type(dependency['version']).__name__}."
            )

    @staticmethod
    def test_dependency_origin_is_path_if_present() -> None:
        """Test that 'origin' is a Path if present in each dependency."""
        debug_info = gather_debug_info()
        for dependency in debug_info["dependencies"]:
            origin = dependency.get("origin")
            assert origin is None or isinstance(origin, Path), (
                "'origin' should be a Path or NoneType in dependency, "
                f"but got {type(dependency.get('origin')).__name__}."
            )
