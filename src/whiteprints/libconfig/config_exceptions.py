# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exception types for Whiteprints configuration loading."""

from typing import Final

from whiteprints.custom_exceptions import WhiteprintsError
from whiteprints.lazy_gettext import _
from whiteprints.redaction import SafeString


__all__: Final = [
    "ConfigDecodeError",
    "ConfigFileAccessError",
    "ConfigLoaderError",
    "ConfigTooLargeError",
]
"""Public module attributes."""


class ConfigLoaderError(WhiteprintsError):
    """An error occured while loading a configuration file."""


class ConfigFileAccessError(ConfigLoaderError):
    """Raised when a configuration file cannot be accessed."""

    def __init__(self, path: SafeString, error: str | None = None) -> None:
        """Init error for inaccessible config file.

        Args:
            path: The file path that failed to open.
            error: The raised exception or error string.
        """
        super().__init__(
            _("Cannot access config file: '{}'{}").format(
                path,
                f"\n{error}" if error else "",
            )
        )
        self.path = path
        self.error = error


class ConfigDecodeError(ConfigLoaderError):
    """Raised when a configuration file is not valid UTF-8."""

    def __init__(self, path: SafeString) -> None:
        """Init error for UTF-8 decoding failure.

        Args:
            path: The file path that could not be decoded.
        """
        super().__init__(_("Config file '{}' is not valid UTF-8").format(path))
        self.path = path


class ConfigParseError(ConfigLoaderError):
    """Raised when a configuration file is not valid UTF-8."""

    def __init__(self, path: SafeString | None) -> None:
        """Init error for UTF-8 decoding failure.

        Args:
            path: The file path that could not be decoded.
        """
        super().__init__(
            _("Malformed TOML configuration file")
            if path is None
            else _("Malformed TOML configuration file '{}'").format(
                path,
            )
        )
        self.path = path


class ConfigTooLargeError(ConfigLoaderError):
    """Raised when the configuration file exceeds the maximum allowed size."""

    def __init__(self, filename: SafeString, size: int, max_size: int) -> None:
        """Init error for oversized config file.

        Args:
            filename: Path to the file.
            size: Actual file size in bytes.
            max_size: Maximum allowed size in bytes.
        """
        super().__init__(
            _("File {} is too large: {} bytes > {} bytes").format(
                filename, size, max_size
            )
        )
        self.filename = filename
        self.size = size
        self.max_size = max_size
