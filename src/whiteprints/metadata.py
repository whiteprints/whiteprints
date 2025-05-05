# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Discover the installed package's metadata from its .dist-info directory.

This module provides fast, read-only access to distribution metadata such as
version, license files, and entry points, assuming the package is installed
using a modern PEP-compliant packaging tool (e.g., pip, build, hatch, poetry).

We deliberately avoid `importlib.metadata` for performance reasons: by scanning
known site-packages locations directly, we bypass internal caching, import
overhead, and entry point resolution logic that is unnecessary in our case.

This implementation assumes the presence of a `.dist-info` directory as
mandated by [PEP 376](https://peps.python.org/pep-0376/) and
[PEP 427](https://peps.python.org/pep-0427/), which define the modern standard
for installed Python distributions. These metadata directories are required for
all compliant wheel installs.

Caveats:
- Packages installed via `setup.py develop` (i.e., legacy `.egg-info`) are
  unsupported.
- Broken or non-standard environments may yield incomplete results.

This module prioritizes startup time and metadata locality over generality or
fallback mechanisms.
"""

import importlib
from functools import cache
from typing import Final, Literal


__all__: Final = [
    "distribution_name",
    "extract_field",
    "extract_fields",
]


def distribution_name() -> str:
    """Return the hard-coded distribution name.

    This is the identifier used to locate the package metadata.

    Returns:
        The name of the distribution, e.g. "whiteprints".
    """
    return "whiteprints"


def _is_dist_info(
    path: str,
    distribution_name: str,
) -> bool:
    """Check if a directory is a dist-info.

    Args:
        path: the directory to check
        distribution_name: The normalized name of the package.

    Returns:
        True if the given path is a dist-info, False otherwise.
    """
    path_name = (
        (os := importlib.import_module("os")).path.basename(path).lower()
    )
    return (
        os.path.isdir(path)
        and path_name.startswith(distribution_name)
        and path_name.endswith("dist-info")
    )


@cache
def _locate_dist_info_directory(distribution_name: str) -> str | None:
    """Locate the .dist-info directory for a given package.

    This function scans `sys.path` for a directory matching the normalized
    name of the distribution and ending in `.dist-info`.

    Args:
        distribution_name: The normalized name of the package.

    Returns:
        The path to the .dist-info directory if found, otherwise None.
    """
    os = importlib.import_module("os")
    return next(
        (
            candidate_path
            for site in importlib.import_module("site").getsitepackages()
            for candidate in os.listdir(site)
            if _is_dist_info(
                candidate_path := os.path.join(site, candidate),
                distribution_name.replace("-", "_").lower(),
            )
        ),
        None,
    )


@cache
def _extract_metadata_fields(
    metadata_text: str,
    field: Literal["Version", "Summary", "License-Expression", "License-File"],
) -> set[str]:
    """Extract all metadata values for a given field.

    This searches for all lines in the metadata text that begin with the
    specified field name followed by a colon.

    Args:
        metadata_text: The raw content of the METADATA file.
        field: The field to search for (e.g., "Version", "License-File").

    Returns:
        A list of field values in order of appearance.
    """
    prefix = f"{field}: "
    return {
        line[len(prefix) :].strip()
        for line in metadata_text.splitlines()
        if line.startswith(prefix)
    }


def extract_fields(
    field: Literal["Version", "Summary", "License-Expression", "License-File"],
) -> set[str]:
    """Extract all values of a specific metadata field from the package.

    The output is cached to avoid re-parsing the METADATA file.

    Args:
        field: One of the allowed metadata fields.

    Returns:
        A list of values found in the METADATA file.
    """
    if not (dist_dir := _locate_dist_info_directory(distribution_name())):
        return set()

    with open(
        importlib.import_module("os").path.join(dist_dir, "METADATA"),
        encoding="utf-8",
    ) as metadata_file:
        text = metadata_file.read()

    return _extract_metadata_fields(
        text,
        field,
    )


@cache
def extract_field(
    field: Literal["Version", "Summary", "License-Expression"],
) -> str | None:
    """Extract a single value for a specific metadata field.

    This is a stricter version of `extract_fields`.

    Args:
        field: One of the allowed metadata fields.

    Returns:
        The field value as a string, or None if zero matches.
    """
    return next(iter(extract_fields(field)), None)
