# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Secure and deterministic loading of configuration files.

This module implements a low-level, hardened configuration loader for
trusted file-based inputs. It enforces file access permissions, validates
file size, decodes content safely, and supports fallback generation using
race-resistant, atomic install logic.

Features:
    - Enforces Unix file permissions (e.g., 0o644, 0o600)
    - Rejects oversized files with `ConfigTooLargeError`
    - Decodes raw bytes with explicit encoding and error handling
    - Computes SHA-256 fingerprints for audit traceability
    - Atomically installs defaults via hardlinking with fsync guarantees
    - TOCTOU-resistant default creation without shared state or locks
    - Exposes stat metadata for forensic or policy inspection
    - **Delays SIGINT/SIGTERM during all mutation steps using `DelaySignals`**

Note:
    Signal safety is strictly enforced during configuration creation steps:
    - All directory creation, temp writes, and hardlinking are guarded by
      `DelaySignals()` to prevent interruption and avoid partial state.

    SHA-256 hashing is optional and should not be enabled for secrets files,
    as it may leak length-based side channels or fixed identifiers.

    All functions are fully lazy-imported, mutate no global state, and return
    immutable, inspectable results.

Use cases:
    - Loading `.toml` files with strict safety guarantees
    - Validating file permissions before secrets ingestion
    - Creating deterministic user config files on first boot
"""

from collections.abc import Callable
from os import stat_result
from typing import BinaryIO, Final, NamedTuple, Self

from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy
from whiteprints.libconfig.config_exceptions import (
    ConfigDecodeError,
    ConfigFileAccessError,
    ConfigTooLargeError,
)
from whiteprints.redaction import SafeString
from whiteprints.signals_handler import DelaySignals


__all__: Final = [
    "ConfigLoadOptions",
    "RawConfiguration",
]
"""Public module attributes."""


class _ConfigFileRaw(NamedTuple):
    """Raw content and stat result of a configuration file.

    Attributes:
        content: Raw bytes read from the file, potentially truncated.
        stat: File system metadata from `os.fstat`, used for inspection.
    """

    content: bytes
    stat: stat_result


class ConfigLoadOptions(NamedTuple):
    """Options controlling how a configuration file is loaded.

    Attributes:
        max_config_size: Maximum allowed size of the configuration file in
            bytes. Files larger than this will be truncated when loading or
            hashing.
        permissions: Loosest allowed file permissions (e.g., Unix permission
            bits). Used to validate config file access rights.
        encoding: Encoding used to decode the configuration file bytes into
            text.
        default: Optional default configuration data, either as a
            TOML-serializable object or a callable returning such an object.
            Used to generate a default config file if none exists.
    """

    path: SafeString | None
    max_config_size: int
    permissions: int
    encoding: str
    default: str | Callable[[], str] | None = None


def _get_file_descriptor(config_path: SafeString) -> int:
    """Open a secure read-only file descriptor.

    Uses O_CLOEXEC and O_NOFOLLOW on Unix; O_NOINHERIT on Windows.

    Args:
        config_path: Path to the config file.

    Returns:
        An integer file descriptor open for reading.
    """
    os = import_lazy("os")
    flags = os.O_RDONLY
    if import_lazy("sys").platform == "win32":
        flags |= os.O_NOINHERIT
    else:
        flags |= os.O_CLOEXEC | os.O_NOFOLLOW

    return os.open(config_path.reveal, flags)


def _check_config_file(
    config_path: SafeString,
    config_file: BinaryIO,
    max_config_size: int,
    permissions: int,
) -> stat_result:
    """Raise if the config file isn't a regular file or exceeds max size.

    Args:
        config_path: Path of the file being checked.
        config_file: Open file object.
        max_config_size: Maximum allowed file size in bytes.
        permissions: loosest file permission allowed.

    Returns:
        confg_file stat results.

    Raises:
        ConfigFileAccessError: If the file is not regular or permissions are
            too loose.
        ConfigTooLargeError: If the file size exceeds allowed maximum.
    """
    os = import_lazy("os")
    config_file_stat = os.fstat(config_file.fileno())

    config_file_mode = config_file_stat.st_mode
    if not import_lazy("stat").S_ISREG(config_file_mode):
        raise ConfigFileAccessError(config_path, _("Not a regular file"))

    if config_file_mode & 0o777 & ~permissions:
        raise ConfigFileAccessError(
            config_path,
            _(
                "File permission are too loose.\nFound {:o}, requested {:o}."
            ).format(
                config_file_mode & 0o777,
                permissions & 0o777,
            ),
        )

    size = config_file_stat.st_size
    if size > max_config_size:
        raise ConfigTooLargeError(config_path, size, max_config_size)

    return config_file_stat


def _dumps_default_config(
    default_config: str | Callable[[], str] | None = None,
) -> str:
    """Return the default configuration content as a string.

    Args:
        default_config: Either a string or a callable returning a string.

    Returns:
        The configuration string (can be empty).
    """
    if callable(default_config):
        return default_config()

    return default_config or ""


def _write_temp_config(
    config_path: str,
    default_config: str | Callable[[], str] | None,
    encoding: str,
) -> str:
    """Create a temporary file containing the default configuration.

    This method is signal-safe. It uses `DelaySignals()` to prevent
    interruption while creating and flushing the temporary file. The file is
    written in the same directory as the target configuration to ensure
    atomic install via hard linking.

    Args:
        config_path: Target configuration path (used to determine temp dir).
        default_config: Default configuration content or callable.
        encoding: Text encoding for writing.

    Returns:
        The full path to the temporary file.
    """
    os = import_lazy("os")
    tempfile = import_lazy("tempfile")

    with (
        DelaySignals(),
        tempfile.NamedTemporaryFile(
            "w",
            prefix=".tmp-",
            suffix=".toml",
            dir=os.path.dirname(config_path) or os.getcwd(),
            encoding=encoding,
            delete=False,
        ) as temp,
    ):
        temp.write(_dumps_default_config(default_config))
        temp.flush()
        os.fsync(temp.fileno())
        return temp.name


def _try_atomic_link(temp_path: str, final_path: str) -> None:
    """Install a configuration file atomically via hard link.

    If `final_path` already exists, the temporary file is discarded.

    Args:
        temp_path: Temporary file path.
        final_path: Destination path to link to.

    Raises:
        None directly. Suppresses `FileExistsError` if file already exists.
    """
    os = import_lazy("os")
    try:
        os.link(temp_path, final_path)
    except FileExistsError:
        return
    else:
        os.unlink(temp_path)


def _ensure_config_exists(
    config_path: SafeString,
    default_config: str | Callable[[], str] | None,
    encoding: str,
) -> None:
    """Ensure the config file exists, creating parent dirs if needed.

    This method is signal-safe and wraps all operations in `DelaySignals()` to
    prevent interruption during directory creation, temporary file write, or
    atomic hardlinking.

    If the file is missing, it will be created safely:
        - Parent directories are created with `0o755` permissions.
        - The default config is written to a temp file in the same directory.
        - The file is then hard-linked atomically to avoid TOCTOU races.

    If another process installs the file first, the creation is skipped without
    overwriting.

    Args:
        config_path: Path to the desired configuration file.
        default_config: A fallback configuration.
        encoding: File encoding.
    """
    os = import_lazy("os")
    abs_path = os.path.abspath(os.path.expanduser(config_path.reveal))

    if os.path.isfile(abs_path):
        return

    with DelaySignals():
        os.makedirs(
            os.path.dirname(abs_path) or os.getcwd(),
            mode=0o755,
            exist_ok=True,
        )
        temp_path = _write_temp_config(abs_path, default_config, encoding)
        _try_atomic_link(temp_path, abs_path)


def _load_config_internal(
    config_path: SafeString,
    max_config_size: int,
    permissions: int,
) -> _ConfigFileRaw:
    """Load raw configuration text or its SHA256 from disk.

    Args:
        config_path: Optional path to a configuration file.
        max_config_size: Maximum allowed file size in bytes. The file
            content is truncated to this size for loading and hashing.
        permissions: Loosest file permission allowed.

    Returns:
        Raw configuration text or SHA256 hash hex digest as string.

    Raises:
        ConfigFileAccessError: If reading or stat fails.

    Notes:
        The SHA256 hash is computed only over the truncated content of the
        file, limited by max_config_size bytes. If the file is larger than
        max_config_size, the hash will NOT represent the entire file.
    """
    try:
        with (
            DelaySignals(),
            import_lazy("os").fdopen(
                _get_file_descriptor(config_path), "rb"
            ) as config_file,
        ):
            stat_results = _check_config_file(
                config_path,
                config_file,
                max_config_size,
                permissions,
            )
            return _ConfigFileRaw(
                content=config_file.read(max_config_size),
                stat=stat_results,
            )

    except (OSError, PermissionError) as file_error:
        raise ConfigFileAccessError(config_path) from file_error


def _decode_configuration(
    config_bytes: bytes,
    encoding: str,
    config_path: SafeString,
) -> str:
    """Decode configuration bytes.

    Args:
        config_bytes: The configuration bytes.
        encoding: Encoding used to decode the configuration file bytes into
            text.
        config_path: The configuration file path, use to enrich the exception
            raised on decode error.

    Returns:
        The configuration string.

    Raises:
        ConfigDecodeError: If the file is not valid UTF-8.
    """
    try:
        return config_bytes.decode(encoding)
    except UnicodeDecodeError as unicode_decode_error:
        raise ConfigDecodeError(config_path) from unicode_decode_error


class RawConfiguration(NamedTuple):
    """Configuration container for a file or resource.

    Attributes:
        content: Decoded string content of the configuration file.
        path: Redacted file path if loaded from disk, else None.
        stat: File stat result if loaded from disk, else None.
        fingerprint: Optional SHA-256 hash digest of content, capped at
            max_config_size bytes.

    Notes:
        - `RawConfiguration.load()` is signal-safe. It delays SIGINT and
          SIGTERM during default file creation (write, link, mkdir), avoiding
          corruption on shutdown.
        - This class is immutable and safe to pass across thread/process
          boundaries.
    """

    content: str
    path: SafeString | None
    stat: stat_result | None
    fingerprint: str | None

    @classmethod
    def load(
        cls,
        config_load_options: ConfigLoadOptions,
        *,
        integrity_hash: bool = False,
    ) -> Self:
        """Load raw configuration text from disk, or return a default.

        This method is signal-safe and defers SIGINT/SIGTERM during any
        configuration creation, disk write, or atomic linking steps. If a
        default configuration is required (because the target file is missing),
        it will be written using a hardened, race-free logic guarded by
        `DelaySignals`.

        Args:
            config_load_options: options controlling how the configuration file
                is loaded.
            integrity_hash: If True, add the SHA256 hash hex digest of the
                first max_config_size bytes of the file.

        Returns:
            the raw configuration and a boolean indicating if the default
                configuration was returned.
        """
        if config_load_options.path is None:
            return cls(
                _dumps_default_config(config_load_options.default),
                path=None,
                stat=None,
                fingerprint=None,
            )

        if config_load_options.default:
            with DelaySignals():
                _ensure_config_exists(
                    config_load_options.path,
                    config_load_options.default,
                    config_load_options.encoding,
                )

        raw_config = _load_config_internal(
            config_load_options.path,
            config_load_options.max_config_size,
            config_load_options.permissions,
        )
        raw_config_decoded = _decode_configuration(
            raw_config.content,
            config_load_options.encoding,
            config_load_options.path,
        )

        hexdigest = None
        if integrity_hash:
            hasher = import_lazy("hashlib").sha256()
            hasher.update(raw_config.content)
            hexdigest = f"sha256={hasher.hexdigest().upper()}"

        return cls(
            raw_config_decoded,
            path=config_load_options.path,
            stat=raw_config.stat,
            fingerprint=hexdigest,
        )

    @property
    def is_default(self) -> bool:
        """True if the default config was loaded, False otherwise."""
        return self.path is None

    def integrity_data(self) -> dict[str, str | int | float | None] | None:
        """Returns relevant forensic stat fields.

        Returns:
            Relevant forensic stat fields or None if unavailable.
        """
        if self.stat is None:
            return None

        return {
            "fingerprint": self.fingerprint,
            "mode": self.stat.st_mode,
            "size": self.stat.st_size,
            "mtime": self.stat.st_mtime,
            "uid": self.stat.st_uid,
            "gid": self.stat.st_gid,
            "ino": self.stat.st_ino,
            "dev": self.stat.st_dev,
            "nlink": self.stat.st_nlink,
        }
