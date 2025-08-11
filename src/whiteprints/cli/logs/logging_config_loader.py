# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Configuration-loading utilities for Whiteprints logging.

This module is responsible for loading, templating, and applying the structured
logging configuration (TOML-based) for Whiteprints. It provides a safe and
predictable mechanism to initialize Python's `logging.config.dictConfig()`.

Key responsibilities:
- Resolves logging config paths via environment and user input.
- Substitutes `$PLACEHOLDER` entries in the TOML with runtime-safe values.
- Validates and parses TOML using a secure, size-limited loader.
- Applies the final logging configuration in a signal-deferred context.

Signal Safety:
- The application of `dictConfig()` is wrapped with `DelaySignals()` to defer
  SIGINT and SIGTERM during critical registration stages.
- This prevents corrupted logger states caused by partial handler installation
  or race conditions between stream setup and signal delivery.
- Only signals received after configuration completes will be delivered.

This guarantees that structured logging can be initialized deterministically,
even when running inside signal-prone environments (e.g., multiprocess CLI,
test harnesses, shell pipelines).

Exports:
- `apply_dict_config`: Applies a prepared TOML dictionary to `logging`.
- `load_config`: Loads the raw config from file or default, performs
  substitutions, and returns a fully-formed configuration.
"""

from collections.abc import Mapping
from string import Template
from typing import Final

from whiteprints.cli.logs.config_interface import LoggingConfiguration
from whiteprints.cli.logs.logging_exceptions import (
    LoadingConfigurationError,
    TemplateSubstitutionError,
)
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libconfig.config_exceptions import (
    ConfigParseError,
)
from whiteprints.libconfig.config_loader import RawConfiguration
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString
from whiteprints.signals_handler import DelaySignals
from whiteprints.toml_types import TOML


__all__: Final = ["apply_dict_config", "load_config"]


def _collect_substitutions(
    raw_config: str,
    log_level: SafeString,
    log_stream: SafeString,
    structured_logs: SafeString,
) -> Mapping[str, SafeString | None]:
    """Build a dict of substitutions for Template(raw_config).substitute().

    Only keys present in the `raw_config` string are returned.

    Args:
        raw_config: The literal TOML template (as-is).
        log_level: Uppercase log level.
        log_stream: The "ext://sys.stdout" or "ext://sys.stderr" string.
        structured_logs: "true" or "false".

    Returns:
        Mapping of placeholder names → replacement values.
    """
    distribution_name = DISTRIBUTION_NAME.upper()
    candidates = {
        f"{distribution_name}_LOG_DIR": import_lazy_project(
            "cli.logs.logs_directories_provider"
        ).user_log_dir(),
        f"{distribution_name}_LOG_TMP_DIR": import_lazy_project(
            "directories_provider"
        ).make_temp_dir("logs"),
        f"{distribution_name}_LOG_LEVEL": log_level,
        f"{distribution_name}_LOG_STREAM": log_stream,
        f"{distribution_name}_LOG_STRUCT": structured_logs,
    }
    return {
        key: value for key, value in candidates.items() if key in raw_config
    }


def reveal_mapping(
    mapping: Mapping[str, SafeString | str | None],
) -> Mapping[str, str | None]:
    """Reveal each field in shallog mapping.

    Args:
        mapping: the shallow mapping to reveal.

    Returns:
        A new structure with the same shape but reveald values.
    """
    return {
        key: value.reveal if isinstance(value, SafeString) else value
        for key, value in mapping.items()
    }


def _resolve_log_config_path(
    config_path: SafeString | None,
    env: Mapping[str, SafeString],
    *,
    fallback: bool,
) -> SafeString | None:
    """Resolve the final configuration path or None if fallback requested.

    Args:
        config_path: User-supplied config file path.
        env: Logging environment mapping.
        fallback: Whether to ignore config_path and use built-in default.

    Returns:
        Final file path to use, or None to signal fallback.
    """
    if fallback:
        return None

    resolver = import_lazy_project("libconfig.config_path_resolver")
    return resolver.resolve_config_file_parameter(
        env,
        "logging.toml",
        config_path,
        f"{DISTRIBUTION_NAME.upper()}_LOG_CONFIG",
        tmpfile_fallback=False,
    )


def _load_raw_log_config(
    path: SafeString | None,
    max_size: int,
) -> RawConfiguration:
    """Load the TOML config content, possibly falling back to default.

    Args:
        path: Path to config file or None.
        max_size: Max bytes allowed.

    Returns:
        RawConfiguration instance.
    """
    loader = import_lazy_project("libconfig.config_loader")
    return loader.RawConfiguration.load(
        loader.ConfigLoadOptions(
            path,
            max_size,
            0o644,
            "UTF-8",
            lambda: import_lazy_project(
                "cli.logs.config_defaults"
            ).DEFAULT_LOG_CONFIG,
        ),
        integrity_hash=True,
    )


def _prepare_log_env(
    env: Mapping[str, SafeString],
) -> tuple[SafeString, SafeString, SafeString]:
    """Extract env vars used in template substitution.

    Args:
        env: Logging environment mapping.

    Returns:
        Tuple of log_level, log_stream, structured_logs.
    """
    logs_env = import_lazy_project("cli.logs.logging_env")
    return (
        logs_env.env_log_level(env),
        logs_env.env_log_stream(env),
        logs_env.env_structured_logs(env),
    )


def _substitute_log_template(
    template_str: str,
    substitutions: Mapping[str, SafeString | str | None],
) -> str:
    """Perform template substitution in the raw TOML.

    Args:
        template_str: The TOML string with $PLACEHOLDER fields.
        substitutions: Mapping from placeholder → value.

    Returns:
        Substituted TOML string.

    Raises:
        TemplateSubstitutionError: On missing key during substitution.
    """
    try:
        return Template(template_str).substitute(reveal_mapping(substitutions))
    except KeyError as key_err:
        missing = key_err.args[0] if key_err.args else "<unknown>"
        raise TemplateSubstitutionError(missing) from key_err


def _parse_log_config(toml_str: str, path: SafeString | None) -> TOML:
    """Parse TOML string into a configuration dictionary.

    Args:
        toml_str: Full substituted TOML content.
        path: Source file path, used for error reporting.

    Returns:
        Python dictionary parsed from TOML.

    Raises:
        ConfigParseError: On TOML syntax failure.
    """
    tomllib = import_lazy("tomllib")
    try:
        return tomllib.loads(toml_str)
    except tomllib.TOMLDecodeError as e:
        raise ConfigParseError(path) from e


def apply_dict_config(config: TOML, path: SafeString | None) -> None:
    """Apply logging configuration safely with signal deferral.

    This function wraps `logging.config.dictConfig()` in a signal-delaying
    context to prevent interruption during handler registration or resource
    setup. Interruptions at this stage (e.g., SIGINT during file handler
    initialization or stream redirection) can lead to undefined logging state,
    unjoinable queues, or silent handler failures.

    Args:
        config: Fully substituted logging configuration dictionary
            (TOML-based).
        path: Optional config source path used for exception context.

    Raises:
        LoadingConfigurationError: If the config is invalid or application
            fails.
    """
    logging_config = import_lazy("logging.config")
    try:
        with DelaySignals():
            logging_config.dictConfig(config)
    except (ValueError, TypeError) as dict_config_error:
        raise LoadingConfigurationError(path) from dict_config_error


def load_config(
    log_config_path: SafeString | None,
    env: Mapping[str, SafeString],
    max_config_size: int,
    *,
    fallback: bool = False,
) -> LoggingConfiguration:
    """Load and apply logging configuration.

    Delegates to modular helpers for:
      - Path resolution
      - Raw file loading
      - Environment evaluation
      - Template substitution
      - TOML parsing
      - Logging configuration injection

    Args:
        log_config_path: Optional path to user-provided logging config.
        env: Environment mapping used for substitutions.
        max_config_size: Maximum size for config file.
        fallback: Force default config if True.

    Returns:
        A `LoggingConfiguration` instance with config, raw text, and
        substitutions.
    """
    path = _resolve_log_config_path(log_config_path, env, fallback=fallback)
    raw_config = _load_raw_log_config(path, max_config_size)
    log_level, log_stream, structured_logs = _prepare_log_env(env)
    substitutions = _collect_substitutions(
        raw_config.content, log_level, log_stream, structured_logs
    )
    substituted = _substitute_log_template(raw_config.content, substitutions)
    config = _parse_log_config(substituted, path)

    return LoggingConfiguration(
        config,
        raw_config,
        substitutions,
        fallback,
    )
