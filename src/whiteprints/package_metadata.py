# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the package's metadata."""

import sys
from functools import cache
from pathlib import Path
from typing import Final, Literal


__all__: Final = [
    "distribution_name",
    "entry_point_name",
    "extract_field",
    "find_license_files",
]


def distribution_name() -> str:
    """Return the hard-coded distribution name.

    This is the identifier used to locate the package metadata.

    Returns:
        The name of the distribution, e.g. "whiteprints".
    """
    return "whiteprints"


def _is_dist_info(
    path: Path,
    distribution_name: str,
) -> bool:
    """Check if a directory is a dist-info.

    Args:
        path: the directory to check
        distribution_name: The normalized name of the package.

    Returns:
        True if the given path is a dist-info, False otherwise.
    """
    return (
        path.is_dir()
        and (name := path.name.lower()).startswith(
            distribution_name.replace("-", "_").lower()
        )
        and name.endswith(".dist-info")
    )


@cache
def _locate_dist_info_directory(distribution_name: str) -> Path | None:
    """Locate the .dist-info directory for a given package.

    This function scans `sys.path` for a directory matching the normalized
    name of the distribution and ending in `.dist-info`.

    Args:
        distribution_name: The normalized name of the package.

    Returns:
        The path to the .dist-info directory if found, otherwise None.
    """
    return next(
        (
            candidate
            for directory in map(Path, sys.path)
            if directory.is_dir()
            for candidate in directory.iterdir()
            if _is_dist_info(candidate, distribution_name)
        ),
        None,
    )


def _extract_metadata_fields(metadata_text: str, field_name: str) -> list[str]:
    """Extract all metadata values for a given field.

    This searches for all lines in the metadata text that begin with the
    specified field name followed by a colon.

    Args:
        metadata_text: The raw content of the METADATA file.
        field_name: The field to search for (e.g., "Version", "License-File").

    Returns:
        A list of field values in order of appearance.
    """
    prefix = f"{field_name}: "
    return [
        line[len(prefix) :].strip()
        for line in metadata_text.splitlines()
        if line.startswith(prefix)
    ]


@cache
def extract_fields(
    field: Literal["Version", "Summary", "License-Expression"],
) -> list[str]:
    """Extract all values of a specific metadata field from the package.

    The output is cached to avoid re-parsing the METADATA file.

    Args:
        field: One of the allowed metadata fields.

    Returns:
        A list of values found in the METADATA file.
    """
    if not (dist_dir := _locate_dist_info_directory(distribution_name())):
        return []

    return _extract_metadata_fields((dist_dir / "METADATA").read_text(), field)


@cache
def extract_field(
    field: Literal["Version", "Summary", "License-Expression"],
) -> str | None:
    """Extract a single value for a specific metadata field.

    This is a stricter version of `extract_fields`, returning only if exactly
    one value is found.

    Args:
        field: One of the allowed metadata fields.

    Returns:
        The field value as a string, or None if zero or multiple matches.
    """
    if len(fields := extract_fields(field)) == 1:
        return fields[0]

    return None


@cache
def find_license_files() -> set[Path]:
    """Find declared license files in the distribution metadata.

    This searches the METADATA file for "License-File" fields and falls back
    to globbing for LICENSE* files if none are declared.

    Returns:
        A set of paths to license files found.
    """
    dist_dir = _locate_dist_info_directory(distribution_name())
    if not dist_dir:
        return set()

    files = _extract_metadata_fields(
        (dist_dir / "METADATA").read_text(), "License-File"
    )
    root = dist_dir.parent
    found = {root / f for f in files if (root / f).is_file()}

    return found or {p for p in root.glob("LICENSE*") if p.is_file()}


@cache
def _read_entry_points(dist_dir: Path) -> list[str]:
    """Read the entry_points.txt file lines.

    Args:
        dist_dir: Path to the .dist-info directory.

    Returns:
        A list of lines from entry_points.txt or an empty list if missing.
    """
    entry_file = dist_dir / "entry_points.txt"
    if entry_file.is_file():
        return entry_file.read_text().splitlines()

    return []


def _extract_console_scripts_section(lines: list[str]) -> list[str]:
    """Extract only the [console_scripts] section.

    This slices the entry points data after the section header, stopping
    at the start of a new section or EOF.

    Args:
        lines: Lines from entry_points.txt.

    Returns:
        A list of lines belonging to [console_scripts].
    """
    section_start = next(
        (
            i + 1
            for i, line in enumerate(lines)
            if line.strip() == "[console_scripts]"
        ),
        None,
    )
    if section_start is None:
        return []

    return [
        line
        for line in lines[section_start:]
        if not line.strip().startswith("[")  # Stop at new section
    ]


def _match_entry_point(lines: list[str], target: str) -> str | None:
    """Match a module:function target against entry point declarations.

    Args:
        lines: Lines from the [console_scripts] section.
        target: The string 'module:function' to match.

    Returns:
        The entry point name if found, otherwise None.
    """
    for line in lines:
        if "=" not in line:
            continue

        name_part, value_part = map(str.strip, line.split("=", 1))
        if value_part == target:
            return name_part

    return None


@cache
def entry_point_name(module_name: str, entrypoint_function: str) -> str | None:
    """Get the name of the console script for a given module:function.

    This scans the [console_scripts] section of entry_points.txt.

    Args:
        module_name: The Python module defining the entry point.
        entrypoint_function: The function used as the entry point.

    Returns:
        The name of the script entry point if found, otherwise None.
    """
    dist_dir = _locate_dist_info_directory(distribution_name())
    if not dist_dir:
        return None

    lines = _read_entry_points(dist_dir)
    console_scripts = _extract_console_scripts_section(lines)
    return _match_entry_point(
        console_scripts, f"{module_name}:{entrypoint_function}"
    )
