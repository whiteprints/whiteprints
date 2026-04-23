# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Minimal, fast access to installed package metadata via .dist-info parsing.

This module locates and parses metadata from the installed .dist-info directory
for a known distribution. It avoids importlib.metadata for performance reasons,
reading only the necessary files via direct sys.path traversal.

Raises:
    MetadataNotFoundError: if the target .dist-info directory cannot be
        located.

Assumes:
    - The package is installed via a modern PEP 376-compliant tool (pip,
      poetry, etc.)
    - A valid .dist-info/METADATA file exists with a properly set 'Name' field

Limitations:
    - Does not support legacy `.egg-info` installs (e.g., `pip install -e .`
      without PEP 660 support)
    - Assumes a `.dist-info` directory is present even in dev mode (as done by
      `uv`, `rye`, etc.)

Notes:
    - All filesystem access is direct (os.open + fdopen) with one-layer
      exception handling
    - Parsing is one-pass and non-caching beyond in-memory @cache decorators
"""

from collections.abc import Iterable
from functools import cache
from io import TextIOWrapper
from types import ModuleType
from typing import Final, Literal

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy
from whiteprints.package_constants import DISTRIBUTION_NAME


__all__: Final = [
    "extract_field",
    "extract_fields",
    "locate_dist_info_directory",
]


class MetadataNotFoundError(WhiteprintsError):
    """Missing .dist-info directory for the current distribution."""

    def __init__(self, distribution_name: str) -> None:
        super().__init__(
            _(".dist-info for {} not found on sys.path").format(
                distribution_name
            )
        )
        self.distribution_name = distribution_name


class MetadataReadError(WhiteprintsError):
    """Raised when the METADATA file cannot be read."""

    def __init__(self, metadata_path: str) -> None:
        super().__init__(
            _("Failed to read METADATA file at {}").format(
                metadata_path,
            )
        )
        self.metadata_path = metadata_path


def normalize(name: str) -> str:
    """Normalize a distribution name.

    Args:
        name: The distribution name to normalize.

    Returns:
        A lowercase, PEP 503-normalized string.
    """
    return name.lower().replace("-", "_").replace(".", "_")


def _is_dist_info(path: str, metadata_name: str) -> bool:
    """Check if a path is a valid .dist-info directory.

    Args:
        path: Filesystem path to check.
        metadata_name: Expected distribution name.

    Returns:
        True if the path is a matching .dist-info directory, False otherwise.
    """
    os = import_lazy("os")
    base = os.path.basename(path)
    if not (os.path.isdir(path) and base.endswith(".dist-info")):
        return False

    stem = base[: -len(".dist-info")]
    parts = stem.split("-")
    if not parts:
        return False

    return normalize(parts[0]) == normalize(metadata_name)


def _parse_metadata_name_from_file(file: TextIOWrapper) -> str | None:
    """Extract 'Name' from an open METADATA file.

    Args:
        file: Open file-like object containing METADATA content.

    Returns:
        Normalized name from the METADATA or None if not found.
    """
    for line in file:
        if line.startswith("Name: "):
            return normalize(line[6:].strip())
    return None


def _read_metadata_name(path: str) -> str | None:
    """Read 'Name' field from a METADATA file.

    Args:
        path: Full path to the METADATA file.

    Returns:
        Normalized name from the file or None if file is unreadable or missing.
    """
    os = import_lazy("os")
    fd = os.open(path, os.O_RDONLY)
    with os.fdopen(fd, "r", encoding="utf-8") as f:
        return _parse_metadata_name_from_file(f)


def _process_entries(
    entries: Iterable[str],
    distribution_name: str,
    base_site_package: str,
    os: ModuleType,
) -> str | None:
    """Search for a matching .dist-info directory in site-packages entries.

    Args:
        entries: List of entries (filenames) under a site-packages path.
        distribution_name: Normalized name of the target distribution.
        base_site_package: Absolute path to the site-packages directory.
        os: Lazily imported os module.

    Returns:
        The full path to the matching .dist-info directory, or None if not
        found.
    """
    for entry in entries:
        path = os.path.join(base_site_package, entry)
        if _is_dist_info(path, DISTRIBUTION_NAME):
            metadata_path = os.path.join(path, "METADATA")
            if _read_metadata_name(metadata_path) == distribution_name:
                return path

    return None


@cache
def _list_site_package_entries(site_package_path: str) -> list[str]:
    """Return cached directory entries for a given site-packages path.

    This function memoizes the result of os.listdir to avoid redundant
    filesystem traversal during .dist-info discovery. It is safe to use
    in CLI contexts with static environments.

    Args:
        site_package_path: Absolute path to a site-packages directory.

    Returns:
        List of directory entries (filenames) under the given path.
    """
    os = import_lazy("os")
    return os.listdir(site_package_path)


@cache
def locate_dist_info_directory() -> str:
    """Find .dist-info path for the current distribution.

    Returns:
        Absolute path to the distribution's .dist-info directory.

    Raises:
        MetadataNotFoundError: If no matching .dist-info directory is found.
    """
    os = import_lazy("os")
    site = import_lazy("site")
    normalized = normalize(DISTRIBUTION_NAME)

    try:
        for base_site_package in site.getsitepackages():
            entries = _list_site_package_entries(base_site_package)
            path = _process_entries(entries, normalized, base_site_package, os)
            if path is not None:
                return path
    except OSError as os_error:
        raise MetadataNotFoundError(DISTRIBUTION_NAME) from os_error

    raise MetadataNotFoundError(DISTRIBUTION_NAME)


@cache
def _load_metadata_text() -> str:
    """Load raw METADATA text.

    Returns:
        Raw text of the METADATA file.

    Raises:
        MetadataReadError: If the METADATA file could not be read.
    """
    os = import_lazy("os")
    metadata_path = os.path.join(locate_dist_info_directory(), "METADATA")
    try:
        fd = os.open(metadata_path, os.O_RDONLY)
        with os.fdopen(fd, "r", encoding="utf-8") as metadata_file:
            return metadata_file.read()
    except OSError as os_error:
        raise MetadataReadError(metadata_path) from os_error


@cache
def _extract_metadata_fields(
    metadata_text: str,
    field: Literal["Version", "Summary", "License-Expression", "License-File"],
) -> set[str]:
    """Extract multiple values for a metadata field.

    Args:
        metadata_text: Full text content of the METADATA file.
        field: Metadata field name to extract.

    Returns:
        A set of all values for the specified field.
    """
    prefix = f"{field}: "
    return {
        line[len(prefix) :].strip()
        for line in metadata_text.splitlines()
        if line.startswith(prefix)
    }


@cache
def extract_fields(
    field: Literal["Version", "Summary", "License-Expression", "License-File"],
) -> set[str]:
    """Return all values for a metadata field.

    Args:
        field: The metadata field name to extract.

    Returns:
        A set of all metadata values found.
    """
    return _extract_metadata_fields(
        _load_metadata_text(),
        field,
    )


@cache
def extract_field(
    field: Literal["Version", "Summary", "License-Expression"],
) -> str | None:
    """Return one value for a metadata field.

    Args:
        field: The metadata field name to extract.

    Returns:
        A single string value if found, otherwise None.
    """
    return next(iter(extract_fields(field)), None)
