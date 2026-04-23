# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Logging system configurator.

This module defines the central `Logging` class responsible for the
declarative initialization, application, and recovery of the logging
infrastructure for CLI invocations.

Unlike ad-hoc `logging.basicConfig()` setups, this configurator is:

- Deterministic: logging configuration is applied exactly once and is guarded
  by a strict lock to avoid race conditions across threads or subprocesses.

- Fork-safe: initialization is lazy and idempotent, preventing duplicate
  configuration across forks or reentrant imports.

- Observability-first: all logging setup (including fallback paths) is
  traceable via structured log records, optionally including raw config
  content and TOML-derived integrity metadata.

- Redaction-aware: all log output — including fallbacks — respects redaction
  boundaries via SafeString and structured extras. Sensitive paths, exception
  messages, and environment variables are never leaked in plaintext.

- Recovery-capable: provides an `emergency_configuration_reset()` API to
  forcibly reset broken handlers, such as orphaned `QueueHandlers`, and
  reestablish fallback logging without requiring process restart.

This configurator is used internally by CLI bootstrapping code and never
relies on side-effectful globals. All initialization requires explicit
environment input and optionally accepts user-defined TOML configurations.

Fallback mode ensures minimum viable logging (to file or stderr) even in the
presence of corrupted configs, missing dependencies, or security-restricted
environments.
"""

from collections.abc import Mapping
from contextlib import AbstractContextManager
from logging import Logger, LogRecord
from typing import ClassVar, Final, TypedDict

from whiteprints.cli.logs.config_interface import LoggingConfiguration
from whiteprints.cli.logs.logging_exceptions import (
    FallbackError,
    LoggingConfigurationError,
    LogLevelError,
    RecursiveFallbackError,
)
from whiteprints.custom_exceptions import format_exception_chain
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libconfig.config_exceptions import ConfigLoaderError
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString
from whiteprints.signals_handler import DelaySignals


__all__: Final = ["Logging", "LoggingState"]


class LoggingState(TypedDict):
    """Serialized state representation for the Logging configurator.

    This dictionary stores the minimal configuration data necessary
    to serialize and deserialize the Logging instance safely.

    Attributes:
        capture_warnings: Flag indicating whether Python warnings are
            captured into the logging system.
        max_config_size: Maximum allowed size (in bytes) for user-supplied
            logging configuration files.
        _configuration: The current logging configuration state,
            or None if not yet configured.
    """

    capture_warnings: bool
    max_config_size: int
    _configuration: LoggingConfiguration | None


class Logging:
    """Logging system configurator.

    This class manages initialization and recovery of the logging system
    for CLI execution.

    Key features:
        - Deterministic: Ensures logging is configured exactly once.
        - Fork- and thread-safe: Only the main thread is allowed to configure
          or mutate the logging system. Other threads may retrieve loggers,
          but cannot trigger configuration or fallback logic.
        - Secure: Redaction-aware and resistant to sensitive leaks.
        - Recoverable: Supports fallback logging and emergency resets.

    Threading model:
        This object must be created and configured by the **main thread**.
        Attempts to initialize, configure, or fallback from non-main threads
        are silently ignored or raise `LoggingNotConfiguredError` when logging
        is accessed too early.

    Attributes:
        capture_warnings: If True, Python warnings are captured into logging.
        max_config_size: Maximum allowed size (in bytes) for TOML configs.
    """

    _MAX_FALLBACK_DEPTH: ClassVar = 2

    def __init__(
        self,
        *,
        capture_warnings: bool = True,
        max_config_size: int = 1_048_576,
        lock: AbstractContextManager[None] | None = None,
    ) -> None:
        """Initialize a Logging instance.

        Args:
            capture_warnings: If True, Python warnings are routed into the
                logging system.
            max_config_size: Maximum number of bytes allowed for a
                user-supplied config TOML.
            lock: a user provided lock to guaratee atomicity and unicity of the
                logging configuration. If None, threading.Lock() will be used.
        """
        self.capture_warnings = capture_warnings
        self.max_config_size = max_config_size
        self.lock = import_lazy("threading").Lock() if lock is None else lock
        self._configuration: LoggingConfiguration | None = None
        with self.lock:
            self._original_log_record_factory = import_lazy(
                "logging"
            ).getLogRecordFactory()
            import_lazy("logging").setLogRecordFactory(
                self._record_factory_with_wall_time
            )

    @property
    def is_configured(self) -> bool:
        """Return True if logging has already been configured."""
        return self._configuration is not None

    def _configure_fallback(
        self,
        env: Mapping[str, SafeString],
    ) -> None:
        """Setup a minimal fallback logger if the primary configuration fails.

        Args:
            env: A mapping of environment variables.

        Raises:
            FallbackError: If fallback configuration also fails.
            LogLevelError: invalid log level is set.
        """
        directories = import_lazy_project("cli.logs.logs_directories_provider")

        logs_env = import_lazy_project("cli.logs.logging_env")
        distribution_name = DISTRIBUTION_NAME.upper()
        fallback_use_envvar = bool(env)
        with DelaySignals():
            try:
                self.configure(
                    env={
                        f"{distribution_name}_LOG_STRUCT": (
                            logs_env.env_structured_logs(env)
                        ),
                        f"{distribution_name}_LOG_DIR": (
                            directories.user_log_dir()
                        ),
                    },
                    log_config_path=None,
                    fallback=True,
                )
            except LoggingConfigurationError as configure_error:
                raise FallbackError from configure_error

            # After configuring fallback, ensure level is valid
            log_level = logs_env.env_log_level(env)
            try:
                self.get_logger(env=env).setLevel(log_level.reveal)
            except (ValueError, TypeError):
                # We raise from None because we do not want to leak the log
                # level name but keep redaction here.
                raise LogLevelError(log_level) from None

        # Log that fallback was used
        self.log_configuration(
            level=30,
            message="fallback logging configured",
            extra={
                "fallback_logger_use_user_environment_variables": (
                    fallback_use_envvar
                )
            },
        )

    def _safe_configure_fallback(self, env: Mapping[str, SafeString]) -> None:
        """Call _configure_fallback safely with fallback depth.

        Args:
            env: A mapping of environment variables.

        Raises:
            RecursiveFallbackError: the fallback configuration has been applied
                too many times.
        """
        with self.lock:
            depth = getattr(self, "_fallback_depth", 0)
            if depth >= self._MAX_FALLBACK_DEPTH:
                raise RecursiveFallbackError(depth)

            self._fallback_depth = depth + 1

        try:
            self._configure_fallback(env)
        finally:
            with self.lock:
                self._fallback_depth -= 1
                if self._fallback_depth == 0:
                    del self._fallback_depth

    def _ensure_logs_directory(self) -> None:
        """Ensure that a log directory exists."""
        if (
            self._configuration
            and "LOG_DIR" in self._configuration.substitutions
        ):
            import_lazy("os").makedirs(
                self._configuration.substitutions["LOG_DIR"],
                mode=0o700,
                exist_ok=True,
            )

    def _log_config_error(
        self,
        configure_value_error: Exception,
        env: Mapping[str, SafeString],
    ) -> None:
        exceptions = import_lazy_project("logs.logs_exceptions")
        logger = self.get_logger(env=env)
        logger.error(
            format_exception_chain(configure_value_error, skip=1),
            **(
                exceptions.LogTraceConfig(stack_info=True, exc_info=True)
                if logger.isEnabledFor(import_lazy("logging").DEBUG)
                else exceptions.LogTraceConfig(
                    stack_info=False, exc_info=False
                )
            ),
        )

    def _apply_config(self, config: LoggingConfiguration) -> None:
        """Safely apply a logging configuration to the global logging system.

        This method ensures the configuration is applied exactly once,
        preserving the idempotency and integrity of the logging configuration
        system.

        Args:
            config: The LoggingConfiguration instance containing
                configuration data and metadata.
        """
        loader = import_lazy_project("cli.logs.logging_config_loader")
        if self._configuration is None:
            with self.lock:
                if self._configuration is None:
                    with DelaySignals():
                        loader.apply_dict_config(
                            config.content, config.raw_content.path
                        )
                        self._configuration = config

    def _record_factory_with_wall_time(
        self, *args: object, **kwargs: object
    ) -> LogRecord:
        """A custom LogRecord factory that adds wall-clock emission time.

        This factory wraps the current logging factory and attaches an
        `emitted_wall_time` attribute (a UNIX timestamp from `time.time()`),
        representing when the log record was created in real time.

        This is useful for measuring end-to-end log latency in asynchronous
        or multi-process setups (e.g., via a logging queue listener).

        Returns:
            A LogRecord instance augmented with `emitted_wall_time`.
        """
        record = self._original_log_record_factory(*args, **kwargs)
        record.emitted_wall_time = import_lazy("time").time()
        return record

    def configure(
        self,
        env: Mapping[str, SafeString],
        log_config_path: SafeString | None = None,
        *,
        fallback: bool = False,
    ) -> None:
        """Thread-safe build (or return) of the logging configuration.

        If already configured, returns the existing LoggingConfiguration.
        Otherwise, attempts to load and apply a TOML config from `log
        `. On failure, falls back to a minimal setup, logs the exception,
        and optionally re-raises.

        Args:up
            env: Environment mapping for substitutions (e.g. LOG_LEVEL,
                LOG_STRUCT).
            log_config_path: Path to a user-supplied TOML file, or None to
                use the built-in defaults.

        Raises:
            LoggingConfigurationError: user logging configuration setup failed.
            ConfigLoaderError: user configuration loading failed.
        """
        if self._configuration is not None:
            return

        with DelaySignals():
            loader = import_lazy_project("cli.logs.logging_config_loader")
            import_lazy("logging").setLogRecordFactory(
                self._record_factory_with_wall_time
            )
            try:
                config = loader.load_config(
                    log_config_path,
                    env,
                    self.max_config_size,
                    fallback=fallback,
                )
                self._apply_config(config)
            except (
                LoggingConfigurationError,
                ConfigLoaderError,
            ) as configure_value_error:
                if not fallback and not isinstance(
                    configure_value_error, RecursiveFallbackError
                ):
                    self._configuration = self._safe_configure_fallback(env)

                self._log_config_error(configure_value_error, env)
                raise

            self._ensure_logs_directory()
            self._capture_warnings()

    def ensure_configured(
        self,
        env: Mapping[str, SafeString],
    ) -> None:
        """Ensure that a logging configuration is in place.

        If not yet configured, calls _safe_configure_fallback to apply built-in
        defaults.

        Args:
            env: A mapping of environment variables.
        """
        with DelaySignals():
            if self._configuration is None:
                try:
                    self._safe_configure_fallback(env)
                except LoggingConfigurationError:
                    self._safe_configure_fallback({})

    def get_logger(
        self,
        main: str | None = None,
        sub: str | None = None,
        env: Mapping[str, SafeString] | None = None,
    ) -> Logger:
        """Return a `logging.Logger` instance for the given hierarchy.

        This method guarantees that logging has been configured by the main
        thread before returning a logger instance. It is safe to call from
        non-main threads **only if** logging was configured first by the main
        thread.

        Args:
            main: The name of the root logger. Defaults to the package's
                DISTRIBUTION_NAME.
            sub: An optional sub-path (e.g. “module.submodule”).
            env: A mapping of environment variables used during configuration,
                ignored if already configured.

        Returns:
            A `logging.Logger` instance corresponding to the requested
            hierarchy.
        """
        if env is None:
            self.ensure_configured(import_lazy_project("cli").ENV)
        else:
            self.ensure_configured(env)

        if main is None:
            main = DISTRIBUTION_NAME

        logging = import_lazy("logging")
        if sub is None:
            return logging.getLogger(main)

        return logging.getLogger(f"{main}.{sub.strip('.')}")

    def log_configuration(
        self,
        message: str = "logging configured",
        level: int = 20,
        env: Mapping[str, SafeString] | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> None:
        """Emit a structured log record containing the active configuration.

        The record's `extra` includes:
          - `config`: a callable that loads the TOML from `raw_config`.
          - `substitution`: the placeholders→values dict.
          - `is_default_config`: bool.

        Args:
            message: The message string to log.
            level: The numeric log level (e.g. logging.DEBUG == 10).
            env: A mapping of environment variables.
            extra: extra arguments to log.
        """
        self.ensure_configured(env or import_lazy_project("cli").ENV)
        if self._configuration is None:
            return

        configuration = self._configuration
        logger = self.get_logger(env=env)
        lazy = import_lazy_project("logs.lazy_logrecord_value")

        logger.log(
            level,
            message,
            extra={
                "config": lazy.LazyRecordValue(
                    import_lazy("tomllib").loads,
                    configuration.raw_content.content,
                ),
                "path": configuration.raw_content.path,
                "file_integrity_data": (
                    configuration.raw_content.integrity_data
                ),
                "substitution": configuration.substitutions,
                "is_fallback": configuration.is_fallback,
                **(extra or {}),
            },
        )

    def emergency_configuration_reset(
        self,
        env: Mapping[str, SafeString] | None = None,
    ) -> None:
        """Emergency override to restore minimal logging.

        This forcibly resets the logging system when the configured
        handlers are non-functional — e.g., if a `QueueHandler` is left
        without a listener, or configuration is corrupted.

        Actions:
          - Removes all handlers from the root logger.
          - Clears all named loggers from the `loggerDict`.
          - Applies a fallback configuration via `_configure_fallback()`.

        Signal safety:
          - This method is signal-safe and wrapped in `DelaySignals` to
            ensure atomic teardown and reconfiguration, especially during
            shutdown or handler death.

        Use this only as a last resort. It bypasses the declarative logging
        model (e.g., dictConfig) and forcefully reinitializes the log stack
        for immediate diagnostic output.

        Warning:
          This method is destructive and should be avoided in normal flow.
        """
        with DelaySignals():
            self._configuration = None
            logging = import_lazy("logging")
            root = logging.root
            while root.handlers:
                root.removeHandler(root.handlers[0])

            root.handlers.clear()
            logging.root.manager.loggerDict.clear()
            if env is None:
                self._safe_configure_fallback(import_lazy_project("cli").ENV)
            else:
                self._safe_configure_fallback(env)

    def _capture_warnings(self) -> None:
        """Optional capturing of Python warnings into the logging system."""
        if self.capture_warnings:
            import_lazy("logging").captureWarnings(capture=True)

    def __getstate__(self) -> LoggingState:
        """Prepare the Logging instance's state for serialization.

        Serializes the minimal required internal state to recreate the Logging
        configurator without including transient or unserializable objects like
        locks.

        Returns:
            A LoggingState dictionary capturing essential configuration state.
        """
        with DelaySignals():
            return LoggingState(
                capture_warnings=self.capture_warnings,
                max_config_size=self.max_config_size,
                _configuration=self._configuration,
            )

    def __setstate__(self, state: LoggingState) -> None:
        """Restore Logging instance from serialized state and reapply config.

        Args:
            state: The serialized LoggingState dictionary.
        """
        with DelaySignals():
            self.capture_warnings = state["capture_warnings"]
            self.max_config_size = state["max_config_size"]
            self.lock = import_lazy("threading").Lock()

            with self.lock:
                self._configuration = None
                logging = import_lazy("logging")
                self._original_log_record_factory = (
                    logging.getLogRecordFactory()
                )
                logging.setLogRecordFactory(
                    self._record_factory_with_wall_time
                )

            if state["_configuration"] is not None:
                self._apply_config(state["_configuration"])
