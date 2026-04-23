# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Resolve configuration file paths using a layered, deterministic strategy.

This module provides a dispatch-based mechanism to locate configuration files
(`*.toml`, `*.conf`, etc.) by querying multiple sources in a fixed priority
order. Each resolver returns a `SafeString` path if its condition is satisfied.

Resolution priority (highest to lowest):

    1. user_input           — Direct SafeString provided (e.g., CLI argument)
    2. env[env_var]         — Redacted value from a declared environment
                              variable
    3. platformdirs         — OS-specific user config directory fallback
    4. tmpfile_fallback     — Temporary config file path (if enabled)

Only the first valid result is returned. If none of the resolvers succeed, the
function returns `None`.

Resolvers:
    - _UserResolver:
        Returns the `user_input` if not None.
    - _EnvResolver:
        Looks up `env[env_var]` if `env_var` is specified and exists.
    - _PlatformdirsResolver:
        If the `platformdirs` extra is available, constructs a path using
        `platformdirs.user_config_dir(DISTRIBUTION_NAME)` and appends the
        default filename. Returned path is redacted and wrapped as `Sensitive`.
    - _TmpfileResolver:
        Generates a temporary path using an internal `directories_provider`.
        This fallback is only active if `tmpfile_fallback=True`.

Security:
    - All resolved paths are wrapped as `SafeString` and may use redaction.
    - Platform-specific paths and temp files are normalized and sanitized.
    - The environment map is expected to already contain redacted keys.
"""

from collections.abc import Mapping
from typing import Final, override

from whiteprints.lazy_import import has_extra, import_lazy, import_lazy_project
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString


__all__: Final = ["resolve_config_file_parameter"]


class _BaseResolver:
    """Abstract base for all config path resolvers."""

    def __call__(
        self,
        env: Mapping[str, SafeString],
        default_config_filename: str,
        user_input: SafeString | None,
        env_var: str | None,
        *,
        tmpfile_fallback: bool,
    ) -> SafeString | None:
        raise NotImplementedError


class _UserResolver(_BaseResolver):
    @override
    def __call__(  # type: ignore[override]
        self,
        env: Mapping[str, SafeString],
        default_config_filename: str,
        user_input: SafeString | None,
        env_var: str | None,
        *,
        tmpfile_fallback: bool,
    ) -> SafeString | None:
        return user_input


class _EnvResolver(_BaseResolver):
    @override
    def __call__(  # type: ignore[override]
        self,
        env: Mapping[str, SafeString],
        default_config_filename: str,
        user_input: SafeString | None,
        env_var: str | None,
        *,
        tmpfile_fallback: bool,
    ) -> SafeString | None:
        return env.get(env_var) if env_var else None


class _PlatformdirsResolver(_BaseResolver):
    @override
    def __call__(  # type: ignore[override]
        self,
        env: Mapping[str, SafeString],
        default_config_filename: str,
        user_input: SafeString | None,
        env_var: str | None,
        *,
        tmpfile_fallback: bool,
    ) -> SafeString | None:
        if not has_extra("platformdirs"):
            return None

        os = import_lazy("os")
        platformdirs = import_lazy("platformdirs")
        redaction = import_lazy_project("redaction")
        return redaction.Sensitive(
            os.path.join(
                platformdirs.user_config_dir(DISTRIBUTION_NAME),
                default_config_filename,
            ),
            import_lazy_project("redactor").PathRedactor(),
            "platformdirs",
        )


class _TmpfileResolver(_BaseResolver):
    @override
    def __call__(  # type: ignore[override]
        self,
        env: Mapping[str, SafeString],
        default_config_filename: str,
        user_input: SafeString | None,
        env_var: str | None,
        tmpfile_fallback: bool,
    ) -> SafeString | None:
        if not tmpfile_fallback:
            return None

        os = import_lazy("os")
        dirs = import_lazy_project("directories_provider")
        tmp_dir = dirs.make_temp_dir("config")
        tmp_path = os.path.join(tmp_dir, default_config_filename)
        tmp_dir.update(tmp_path)
        return tmp_dir


_RESOLVER: list[_BaseResolver] = [
    _UserResolver(),
    _EnvResolver(),
    _PlatformdirsResolver(),
    _TmpfileResolver(),
]


def resolve_config_file_parameter(
    env: Mapping[str, SafeString],
    default_config_filename: str,
    user_input: SafeString | None = None,
    env_var: str | None = None,
    *,
    tmpfile_fallback: bool = False,
) -> SafeString | None:
    """Resolve a configuration file.

    Resolve a configuration file path from multiple sources in priority order.

    1. explicit user_input
    2. env[env_var]
    3. platformdirs.user_config_dir
    4. ephemeral tempdir (if tmpfile_fallback)

    Returns:
        a safe string to the configuration file.
    """
    for resolver in _RESOLVER:
        result = resolver(
            env,
            default_config_filename,
            user_input,
            env_var,
            tmpfile_fallback=tmpfile_fallback,
        )
        if result is not None:
            return result

    return None
