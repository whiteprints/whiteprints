# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""8-layer environment resolution with TOML-based configuration and redaction.

This module implements a deterministic environment model based on TOML
configuration files, declared redaction policies, and file permission
validation. It flattens structured configuration into uppercase,
underscore-delimited key-value pairs suitable for use in `os.environ`.

Environment resolution is ordered across **eight strict precedence layers**:

    1. Filtered process environment (`os.environ`), using whitelist or regex
    2. `env.dev.toml`             — developer defaults (644)
    3. `env.toml`                 — project defaults (644)
    4. `env.staging.toml`         — staging/test overrides (644),
    runtime_checkable
    5. `env.production.toml`      — production overrides (644)
    6. `secrets.local.toml`       — development secrets (600)
    7. `secrets.toml`             — project-level secrets (600)
    8. `secrets.override.toml`    — critical/override secrets (600)

Later layers override earlier ones when keys conflict.

Redaction and security enforcement:
    - Files are validated for correct permissions (`0o644` or `0o600`)
    - Declared secrets in public files raise `UnsafeVariableError`
    - Redaction wrappers (`Clear`, `Sensitive`, `Secret`) control visibility
    - Values can be transformed before redaction using user-defined functions
    - All values are coerced to strings; `None` is skipped

Flattening behavior:
    - Nested keys are joined using `_` and uppercased
    - Lists are indexed numerically
    - TOML datetimes are formatted as RFC 3339 (ISO 8601)
    - An optional prefix can be prepended to all keys

Example TOML input:

    [service]
    name = "api"
    ports = [8000, 8001]

    [build]
    date = 2025-06-01T12:00:00Z

Produces environment variables:

    SERVICE_NAME = "api"
    SERVICE_PORTS_0 = "8000"
    SERVICE_PORTS_1 = "8001"
    BUILD_DATE = "2025-06-01T12:00:00+00:00"

Path resolution strategy:
    The function `resolve_env_file_path(filename)` is used to locate each
    environment or secrets file before parsing. It first checks for an override
    environment variable named `<DISTRO>_<STEM>_FILE`, where `<STEM>` is the
    filename's stem in uppercase (e.g., `MYPROGRAM_ENV_FILE`). If this is
    unset or invalid, it falls back to a dot-prefixed file in the current
    working directory (e.g., `./.env.toml`). All paths are redacted before use,
    and resolution is delegated to the platform-aware dispatcher in
    `libconfig.config_path_resolver`.

This module:
    - Does not mutate `os.environ`
    - Does not parse raw TOML (delegates to trusted config loader)
    - Enforces strict configuration boundaries and visibility guarantees
"""

from collections.abc import Callable, Iterator, Mapping
from functools import cached_property
from logging import Logger
from types import MappingProxyType, ModuleType
from typing import ClassVar, Final, TypedDict, cast, override

from whiteprints.custom_exceptions import (
    WhiteprintsError,
    format_exception_chain,
)
from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy, import_lazy_project
from whiteprints.libconfig.config_exceptions import ConfigParseError
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.redaction import SafeString
from whiteprints.redactor import BaseRedactor
from whiteprints.signals_handler import DelaySignals
from whiteprints.toml_types import TOML


__all__: Final = [
    "MAX_ENV_FILE_SIZE",
    "MAX_SECRETS_FILE_SIZE",
    "Environment",
    "UnsafeVariableError",
    "abort_on_error",
]
"""Public module attributes."""


MAX_ENV_FILE_SIZE: Final = 1_048_576
"""1 MiB cap for regular env files"""

MAX_SECRETS_FILE_SIZE: Final = 67_108_864
"""64 MiB cap for secrets files"""


class UnsafeVariableError(WhiteprintsError):
    """Secret was loaded from an unsafe source."""

    def __init__(self, key: SafeString) -> None:
        """Create an UnsafeVariableError instance.

        Args:
            key: the key loaded.
            source: the source of the loaded key.
        """
        super().__init__(
            _("{} cannot be loaded from untrusted file {}").format(
                key,
                key.origin,
            )
        )
        self.key = key


class EnvironmentState(TypedDict):
    environment_variables: list[str]
    environment_variables_regex: list[str]
    sensitive_variables: dict[str, BaseRedactor]
    secret_variables: list[str]
    transform_variables: dict[str, BaseRedactor]

    _variables: list[str]
    _environ: dict[str, SafeString]
    _environ_file: dict[str, SafeString]
    _environ_secrets: dict[str, SafeString]


def _process_list(
    key: str,
    value: list[TOML],
    stack: list[tuple[str, TOML]],
    sep: str,
) -> None:
    """Push list elements onto the stack with appropriately formatted keys.

    Each element in the list is assigned a key formed by appending the index to
    the current key using the separator, uppercased.

    Args:
        key: The current key prefix for nested values.
        value: The list of NOML nodes to process.
        stack: The stack holding (key, value) pairs to process.
        sep: The separator string used to join nested keys.
    """
    for i, item in enumerate(value):
        full_key = f"{key}{sep}{i}".upper()
        stack.append((full_key, item))


def _process_dict(
    key: str,
    value: Mapping[str, TOML],
    stack: list[tuple[str, TOML]],
    sep: str,
) -> None:
    """Push dictionary items onto the stack with appropriately formatted keys.

    Each key in the dictionary is appended to the current key prefix using the
    separator, then uppercased.

    Args:
        key: The current key prefix for nested values.
        value: The dictionary of TOML nodes to process.
        stack: The stack holding (key, value) pairs to process.
        sep: The separator string used to join nested keys.
    """
    for new_key, new_value in value.items():
        full_key = f"{key}{sep}{new_key}".upper()
        stack.append((full_key, new_value))


def _process_data(
    stack: list[tuple[str, TOML]],
    sep: str,
) -> Iterator[tuple[str, str]]:
    """Process the top item on the stack, flattening TOML nodes into env vars.

    Pops one (key, value) pair from the stack and processes it according to its
    type: recursively pushes dicts and lists back onto the stack, or stores
    scalars in the result dictionary.

    Args:
        stack: The stack of (key, value) pairs to process.
        sep: The separator string used to join nested keys.

    Yields:
        A flatten key, value pair.
    """
    key, value = stack.pop()
    cur_sep = sep if key else ""
    match value:
        case dict():
            _process_dict(key, value, stack, cur_sep)
        case list():
            _process_list(key, value, stack, cur_sep)
        case _:
            yield key.upper(), str(value)


def to_env(
    data: TOML, prefix: str = "", sep: str = "_"
) -> Iterator[tuple[str, str]]:
    """Flatten a TOML-like structure into a flat mapping with uppercase keys.

    Suitable for setting environment variables.

    Args:
        data: A nested dict or list conforming to TOML structure.
        prefix: Optional prefix to prepend to all keys.
        sep: The nested key name separator.

    Yields:
        A flat dict mapping uppercased keys to string values.
    """
    stack: list[tuple[str, TOML]] = [(prefix, data)]
    while stack:
        yield from _process_data(stack, sep)


def _parse_env_file(
    file_path: SafeString,
    max_config_size: int,
    permissions: int,
    *,
    integrity_hash: bool,
) -> Iterator[tuple[str, str]]:
    """Parse a TOML file and return its contents as environment variables.

    Args:
        file_path: The resolved path to the file.
        max_config_size: Maximum allowable file size.
        permissions: Expected file permission mask.
        integrity_hash: Whether to compute an integrity hash of the file.

    Yields:
        Tuples of (key, value) for each environment variable.

    Raises:
        ConfigParseError: If the TOML is malformed.
    """
    os = import_lazy("os")
    loader = import_lazy_project("libconfig.config_loader")
    tomllib = import_lazy("tomllib")

    if not os.path.isfile(file_path.reveal):
        return

    config = loader.RawConfiguration.load(
        loader.ConfigLoadOptions(
            file_path,
            max_config_size,
            permissions,
            encoding="UTF-8",
            default=None,
        ),
        integrity_hash=integrity_hash,
    )

    try:
        data = tomllib.loads(config.content)
    except tomllib.TOMLDecodeError as toml_error:
        raise ConfigParseError(file_path) from toml_error

    yield from to_env(data)


def resolve_env_file_path(filename: str) -> SafeString | None:
    """Resolve the environment configuration file path.

    Resolution order favors explicit developer intent, with priority as
    follows:

        1. A configured override via environment variable
           (e.g. `<DISTRIBUTION>_<STEM>_FILE`)
        2. A dot-prefixed file in the current working directory (e.g.
           `./.env.toml`)
        3. A fallback to `platformdirs.user_config_dir()/<filename>`

    Args:
        filename: The base name of the configuration file.

    Returns:
        A redacted path or None if no valid file is found.
    """
    os = import_lazy("os")
    redaction = import_lazy_project("redaction")
    redactor = import_lazy_project("redactor")
    resolver = import_lazy_project("libconfig.config_path_resolver")

    local_env_file = os.path.normcase(
        os.path.expanduser(os.path.join(os.getcwd(), f".{filename}"))
    )
    stem = os.path.splitext(os.path.basename(filename))[0].upper()
    key = f"{DISTRIBUTION_NAME.upper()}_{stem.replace('.', '_')}_FILE"

    env_paths = (
        {
            key: redaction.Sensitive(
                os.environ[key], redactor.PathRedactor(), "os.environ"
            )
        }
        if key in os.environ
        else {}
    )

    fallback = (
        redaction.Sensitive(local_env_file, redactor.PathRedactor(), "default")
        if os.path.isfile(local_env_file)
        else None
    )

    return resolver.resolve_config_file_parameter(
        env_paths, filename, None if env_paths else fallback, key
    )


def load_conf_env(
    file_path: SafeString,
    max_config_size: int,
    permissions: int,
    *,
    integrity_hash: bool,
) -> Iterator[tuple[str, str]]:
    """Load key-value pairs from a TOML environment file.

    Args:
        file_path: The name of the TOML file to load.
        max_config_size: The maximum allowed size of the file in bytes.
        permissions: The required file permission mask (e.g., 0o600).
        integrity_hash: Whether to compute an integrity hash of the file.

    Yields:
        Tuples of (key, value) from the environment file.
    """
    yield from _parse_env_file(
        file_path, max_config_size, permissions, integrity_hash=integrity_hash
    )


class Environment(Mapping[str, SafeString]):
    """Singleton environment with layered configuration sources.

    Provides a mapping interface with lazy loading and caching for each layer.

    Note:
        This class is process-local and intentionally non-picklable. It should
        not be instantiated or accessed in child processes (via `fork` or
        `spawn`), as this will re-parse configuration files and re-read
        `os.environ`, potentially introducing inconsistencies and performance
        overhead.

        Instead, resolve all required environment values in the parent process
        and pass them explicitly to child processes. This avoids redundant I/O,
        ensures configuration determinism, and maintains environment integrity
        across the process boundary.
    """

    ENV_FILE_NAMES: ClassVar[list[str]] = [
        "env.dev.toml",  # lowest
        "env.toml",
        "env.staging.toml",
        "env.production.toml",  # highest
    ]
    """List of 644-permission environment configuration files.

    These files are layered in descending priority order for non-sensitive
    configuration. Later files override earlier ones if a key is duplicated.

    Priority (highest to lowest):
        1. env.production.toml  - Production-specific settings
        2. env.staging.toml     - Staging/testing environment overrides
        3. env.toml             - Base/default configuration
        4. env.dev.toml         - Developer-specific overrides
    """

    SECRETS_FILE_NAMES: ClassVar[list[str]] = [
        "secrets.local.toml",  # lowest
        "secrets.toml",
        "secrets.override.toml",  # highest
    ]
    """List of 600-permission secrets configuration files.

    These files are layered in descending priority order for sensitive data
    (credentials, tokens, secrets). Later files override earlier ones if a
    key is duplicated.

    Priority (highest to lowest):
        1. secrets.override.toml    - Emergency overrides and critical patches
        2. secrets.toml             - Canonical deployment-provided secrets
        3. secrets.local.toml       - Developer sandbox secrets (lowest trust)
    """

    def __init__(
        self,
        environment_variables: set[str],
        environment_variables_regex: set[str],
        sensitive_variables: Mapping[str, BaseRedactor],
        secret_variables: set[str],
        transform_variables: Mapping[
            str,
            BaseRedactor | Callable[[str], str],
        ],
    ) -> None:
        """Initialize Environment with variable sets and transformation rules.

        Args:
            environment_variables: Set of base variable names used for
                filtering.
            environment_variables_regex: Set of base variable regex used for
                filtering.
            sensitive_variables: Mapping of variable names to redactor
                factories.
            secret_variables: Set of secret variables.
            transform_variables: Mapping of variable names to transformation
                functions.
        """
        self.environment_variables = environment_variables
        self.environment_variables_regex = environment_variables_regex
        self.sensitive_variables = sensitive_variables
        self.secret_variables = secret_variables
        self.transform_variables = transform_variables
        self.errors: list[WhiteprintsError] = []
        self._logger: Logger | None = None

    def set_logger(self, logger: Logger) -> None:
        """Set a logger to the Environment.

        Args:
            logger: A logger instance used for emitting debug information
                from the Environment.

        Note:
            If using `multiprocessing`, ensure the logger is safe across
            process boundaries. Standard loggers may duplicate open file
            descriptors or internal locks, which can cause data corruption or
            deadlocks.

            Recommended options:
                - Use `reset_logger()` after forking or spawning to clear
                  inherited state.
                - Prefer a `QueueHandler` with a `QueueListener` to isolate
                  logging in a dedicated process, which is robust across both
                  `fork` and `spawn`.

            As of Python 3.8+, `spawn` is the default on macOS and Windows,
            and optionally used on Unix systems for improved safety.
        """
        self._logger = logger

    def reset_logger(self) -> None:
        """Clear the current logger reference.

        This is useful in multiprocessing contexts to prevent inherited loggers
        (which may reference unsafe file descriptors or internal thread state)
        from being reused in child processes.
        """
        self._logger = None

    @property
    def logger_not_set(self) -> bool:
        """Check whether the logger is not set."""
        return self._logger is None

    @cached_property
    def _fullmatch(self) -> Callable[[str], bool] | None:
        if self.environment_variables_regex:
            union = "|".join(
                f"(?:{pat})" for pat in self.environment_variables_regex
            )
            return import_lazy("re").compile(f"^(?:{union})$").fullmatch

        return None

    @cached_property
    def _variables(self) -> frozenset[str]:
        """All known environment variable keys across all sources."""
        return frozenset(
            variable
            for variables in (
                self._environ,
                self._environ_file,
                self._environ_secrets,
            )
            for variable in variables
        )

    def log_debug(self) -> None:
        """Log the current internal environment state at debug level."""
        if self._logger is not None:
            self._logger.debug(
                "Environment status",
                extra={
                    "variables": set(self._variables),
                    "environ": dict(self._environ),
                    "environ_file": dict(self._environ_file),
                    "environ_secrets": dict(self._environ_secrets),
                },
            )

    def _matches(self, key: str) -> bool:
        """Check if a key matches the configured regex filters.

        Args:
            key: Environment variable name to check.

        Returns:
            True if the key matches a regex filter, False otherwise.
        """
        if self._fullmatch:
            return bool(self._fullmatch(key))

        return False

    def _should_include(self, key: str) -> bool:
        """Determine if a variable should be included in configuration.

        This considers both exact matches and regex matches.

        Args:
            key: Environment variable name to evaluate.

        Returns:
            True if the variable should be included.
        """
        return key in self.environment_variables or (
            self._fullmatch is not None and self._matches(key)
        )

    def _collect_regex_matched_environment(
        self,
        env: Mapping[str, str],
        redaction: ModuleType,
        out: dict[str, SafeString],
    ) -> None:
        """Collect environment variables matched by regex, if enabled.

        Adds variables not already in `out` and matched by the regex pattern
        provided via `self._matches`.

        Args:
            env: A dictionary of environment variables.
            out: The current output mapping to populate.
            redaction: The redaction module providing `Sensitive` and `Clear`.
        """
        for key, val in env.items():
            if key not in out and self._matches(key):
                out[key] = self._redact(key, val, redaction, "os.environ")

    def _redact(
        self, key: str, val: str, redaction: ModuleType, filename: str
    ) -> SafeString:
        """Transform and redact a single environment variable.

        Applies transformation to the value and wraps it using either the
        `Sensitive` or `Clear` class depending on whether the key is marked
        sensitive.

        Args:
            key: The environment variable name.
            val: The raw value of the variable.
            redaction: The redaction module providing `Sensitive` and `Clear`.
            filename: The origin filename.

        Returns:
            A redacted or clear `SafeString` instance.
        """
        transformed = self._transform(key, val)
        label = self.sensitive_variables.get(key)
        if label is not None:
            return redaction.Sensitive(transformed, label, filename)

        return redaction.Clear(transformed, filename)

    def _secretify(
        self, key: str, val: str, redaction: ModuleType, filename: str
    ) -> SafeString:
        """Transform and wrap a secret environment variable.

        Args:
            key: The environment variable name.
            val: The environment variable value.
            redaction: The redaction module (lazy-loaded).
            filename: The origin filename.

        Returns:
            A redacted `Secret` instance.
        """
        return redaction.Secret(self._transform(key, val), key, filename)

    def _collect_explicit_environment(
        self,
        env: Mapping[str, str],
        redaction: ModuleType,
    ) -> dict[str, SafeString]:
        """Collect explicitly listed environment variables.

        Looks up each key in `self.environment_variables`, transforms its
        value, and applies redaction if marked as sensitive. Skips unset
        variables.

        Args:
            env: A dictionary of environment variables (typically
                `os.environ`).
            redaction: The redaction module providing `Sensitive` and `Clear`.

        Returns:
            A dictionary mapping keys to secret `SafeString` values.
        """
        out: dict[str, SafeString] = {}
        for key in self.environment_variables:
            val = env.get(key)
            if val is not None:
                out[key] = (
                    self._secretify(key, val, redaction, "os.environ")
                    if key in self.secret_variables
                    else self._redact(key, val, redaction, "os.environ")
                )

        return out

    @cached_property
    def _environ(self) -> MappingProxyType[str, SafeString]:
        """Builds an immutable mapping of  environment variables.

        Environment variables listed in `self.environment_variables` are
        looked up, transformed using `self._transform`, and optionally redacted
        if marked as sensitive in `self.sensitive_variables`.

        If `self._fullmatch` is enabled, additional variables matched by the
        configured regex are included, provided they weren't already explicitly
        listed.

        Returns:
            An immutable mapping of environment variables as `SafeString`
            instances, either redacted or clear depending on sensitivity.
        """
        os = import_lazy("os")
        redaction = import_lazy_project("redaction")

        out = self._collect_explicit_environment(os.environ, redaction)
        if self._fullmatch:
            self._collect_regex_matched_environment(os.environ, redaction, out)

        return MappingProxyType(out)

    def _handle_env_variable(
        self,
        key: str,
        val: str,
        filename: str,
        file_path: SafeString,
        out: dict[str, SafeString],
    ) -> None:
        """Classify and insert an environment variable based on sensitivity.

        Redacts and stores the variable if allowed. If the key is marked as a
        secret but is found in a non-secret config file, registers an
        exception.

        Args:
            key: The environment variable name.
            val: The value of the environment variable.
            filename: The name of the file from which this key was read.
            file_path: The redacted SafeString path object.
            out: A mutable dictionary where validated variables are stored.

        Side Effects:
            - Updates `self.errors` with an `UnsafeVariableError` if a
              secret variable is loaded from an untrusted file.
        """
        if not self._should_include(key):
            return

        redaction = import_lazy_project("redaction")

        if key in self.secret_variables:
            self.errors.append(
                UnsafeVariableError(redaction.Secret(val, key, file_path))
            )
            return

        out[key] = self._redact(key, val, redaction, filename)

    def _process_env_file(
        self, filename: str, out: dict[str, SafeString]
    ) -> None:
        """Process a single non-secret environment file and extract key-values.

        Attempts to resolve the file path and load TOML data if present and
        valid. Redacts or rejects variables based on their classification.

        Args:
            filename: The base filename to resolve and load.
            out: The mutable dictionary to populate with safe environment
                variables.

        Note:
            - Populates `out` with valid environment variables.
            - Sets `self.errors` if parsing fails or a secret is loaded from
              an untrusted file.
        """
        try:
            file_path = resolve_env_file_path(filename)
            if file_path is None:
                return

            data = load_conf_env(
                file_path,
                MAX_ENV_FILE_SIZE,
                0o644,
                integrity_hash=True,
            )

            for key, val in data:
                self._handle_env_variable(key, val, filename, file_path, out)

        except import_lazy_project(
            "libconfig.config_exceptions"
        ).ConfigLoaderError as err:
            self.errors.append(err)

    @cached_property
    def _environ_file(self) -> MappingProxyType[str, SafeString]:
        """Parse and redact environment variables from configuration files.

        Iterates over the list of allowed configuration files
        (`ENV_FILE_NAMES`) and attempts to load, parse, and redact their
        contents according to the declared sensitivity of each variable. If a
        variable is declared as a secret but appears in a non-secret file, an
        `UnsafeVariableError` is recorded in `self.errors`.

        Returns:
            An immutable mapping of redacted environment variables collected
            from trusted, non-secret sources.
        """
        out: dict[str, SafeString] = {}
        for filename in self.ENV_FILE_NAMES:
            self._process_env_file(filename, out)

        return MappingProxyType(out)

    def _handle_secret_variable(
        self,
        key: str,
        val: str,
        filename: str,
        out: dict[str, SafeString],
    ) -> None:
        """Filter and store a secret environment variable if allowed.

        Args:
            key: The variable name.
            val: The raw string value.
            filename: The filename the variable was loaded from.
            out: The mutable dictionary to populate.
        """
        if not self._should_include(key):
            return

        redaction = import_lazy_project("redaction")
        out[key] = self._secretify(key, val, redaction, filename)

    def _process_secrets_file(
        self, filename: str, out: dict[str, SafeString]
    ) -> None:
        """Process a single secrets file and populate the output dictionary.

        Attempts to resolve and parse the specified secrets file. Extracted
        key-value pairs are transformed and wrapped as `Secret` objects if they
        pass inclusion criteria.

        Args:
            filename: The base filename of the secrets TOML file.
            out: A mutable dictionary where parsed secrets will be stored.

        Side Effects:
            - Modifies `out` with valid redacted secrets.
            - Sets `self.errors` on failure to load or parse the file.
        """
        try:
            file_path = resolve_env_file_path(filename)
            if file_path is None:
                return

            data = load_conf_env(
                file_path,
                MAX_SECRETS_FILE_SIZE,
                0o600,
                integrity_hash=False,
            )

            for key, val in data:
                self._handle_secret_variable(key, val, filename, out)

        except import_lazy_project(
            "libconfig.config_exceptions"
        ).ConfigLoaderError as err:
            self.errors.append(err)

    @cached_property
    def _environ_secrets(self) -> MappingProxyType[str, SafeString]:
        """Load and redact secret environment variables from files.

        This method processes all known secret config files (defined in
        `SECRETS_FILE_NAMES`), parsing each TOML file and extracting key-value
        pairs marked as secrets. These variables are wrapped as `Secret`
        instances and returned as a read-only mapping.

        If any file fails to load due to format or permission issues, the
        exception is captured in `self.errors` and an empty mapping is
        returned.

        Returns:
            An immutable mapping of secret environment variables with redacted
            values.
        """
        out: dict[str, SafeString] = {}
        for filename in self.SECRETS_FILE_NAMES:
            self._process_secrets_file(filename, out)

        return MappingProxyType(out)

    def _getitem_secret_file(self, key: str) -> SafeString:
        """Retrieve a secret variable from the secrets file layer.

        Logs access if a logger is set.

        Args:
            key: The name of the environment variable.

        Returns:
            The corresponding redacted `SafeString`.
        """
        value = self._environ_secrets[key]
        if self._logger is not None:
            self._logger.debug(
                _("file secret variable fetched"),
                extra={"key": key, "value": value},
            )

        return value

    def _getitem_environ_file(self, key: str) -> SafeString:
        """Retrieve a environment variable from the environment file layer.

        Logs access if a logger is set.

        Args:
            key: The name of the environment variable.

        Returns:
            The corresponding redacted `SafeString`.
        """
        value = self._environ_file[key]
        if self._logger is not None:
            self._logger.debug(
                _("file environment variable fetched"),
                extra={"key": key, "value": value},
            )

        return value

    def _getitem_environ(self, key: str) -> SafeString:
        """Retrieve a environment variable from the os environment layer.

        Logs access if a logger is set.

        Args:
            key: The name of the environment variable.

        Returns:
            The corresponding redacted `SafeString`.
        """
        value = self._environ[key]
        if self._logger is not None:
            self._logger.debug(
                _("os environment variable fetched"),
                extra={"key": key, "value": value},
            )

        return value

    @override
    def __getitem__(self, key: str) -> SafeString:
        with DelaySignals():
            if key in self._environ_secrets:
                return self._getitem_secret_file(key)

            if key in self._environ_file:
                return self._getitem_environ_file(key)

            if key in self._environ:
                return self._getitem_environ(key)

            raise KeyError(key)

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(self._variables)

    @override
    def __len__(self) -> int:
        return len(self._variables)

    def _transform(self, key: str, value: str) -> str:
        """Apply transformation function if configured for the key.

        Args:
            key: The environment variable key to transform.
            value: The raw string value to transform.

        Returns:
            The transformed string value.
        """
        fn = self.transform_variables.get(key)
        return fn(value) if fn else str(value)

    def validate(self) -> None:
        """Eagerly validate that required environment variables are present."""
        _ = self._variables
        if self.errors:
            raise self.errors[0]

    def abort_on_error(self) -> None:
        """Abort the process if a configuration loading error occurred.

        If an exception was raised during the loading of environment or secrets
        files, this method will log the error and exit the process with a
        configuration-specific ExitCode.

        This should be called after instantiating the environment, for example
        after `validate()` to ensure all necessary variables are resolved.

        Note:
            This method is non-returning only if a configuration error was
            encountered. If no error is present, it simply returns.
        """
        if not self.errors:
            return

        exit_code = cast(
            "ExitCode", import_lazy_project("exit_codes").CONFIGURATION_ERROR
        )
        if self._logger is not None:
            for err in self.errors:
                self._logger.critical(format_exception_chain(err))

            exit_code.log(self._logger)

        exit_code.exit(self.errors[0])


def abort_on_error(
    env: Mapping[str, SafeString],
    logger: Callable[[], Logger],
) -> None:
    """Abort the process if the provided environment has errors.

    Wrapper function that checks whether the given environment is an instance
    of `Environment` and has a recorded configuration error. If so, it sets a
    logger (if not already set), logs the full error chain, and exits.

    Note:
        This function is non-returning only if a configuration error was
        encountered. If no error is present, it simply returns.

    Args:
        env: The environment mapping to inspect.
        logger: Thunk that returns a logger instance, evaluated only if needed.
    """
    if isinstance(env, Environment) and env.errors:
        if env.logger_not_set:
            env.set_logger(logger())

        env.abort_on_error()
