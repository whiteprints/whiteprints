# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Modular redaction system for structured log sanitization.

This module defines a set of pluggable redactors used to sanitize sensitive
information in strings before emitting them to structured log outputs.
Each redactor is a callable that transforms input text to obfuscate or
replace confidential data such as email addresses, IPs, filesystem paths,
MAC addresses, etc.

Design Principles:
  - Stateless, lazy, and cacheable regular expressions where applicable.
  - Composition via `UnionRedactor` to chain transformations.
  - Normalized path resolution for cross-platform redaction fidelity.
  - Opt-in subclassing of `BaseRedactor` with an overridable `redact()`.

Example:
    >>> redact = UnionRedactor([EmailRedactor(), IPRedactor()])
    >>> redact("user@example.com accessed 10.0.0.1")
    '<Redacted:EMAIL> accessed <Redacted:IP>'
"""

from collections.abc import Callable, Iterable, Mapping
from functools import cache, cached_property
from typing import Final, override

from whiteprints.lazy_import import import_lazy


__all__: Final = [
    "EmailRedactor",
    "IPRedactor",
    "MACRedactor",
    "PathRedactor",
    "UnionRedactor",
]
"""Public module attributes."""


class BaseRedactor:
    """Base class for redactors.

    A redactor is a callable object that transforms a string for redaction,
    obfuscation, or sanitization. Subclasses should override `redact()`,
    which by default returns an "****" string to signal complete redaction.

    The `__call__()` method delegates to `redact()` to enable functional use.

    This class avoids ABCs or abstractmethods and is fully instantiable.
    """

    __slots__ = ()

    def redact(self, data: str) -> str:
        """Redact the input string.

        Args:
            data: The string to redact.

        Returns:
            A masked version of the input (e.g., '*****').
        """
        _self, _data = self, data
        return "****"

    def __call__(self, data: str) -> str:
        """Apply redaction.

        Args:
            data: The input string.

        Returns:
            The redacted result.
        """
        return self.redact(data)


class PathRedactor(BaseRedactor):
    """Redacts sensitive filesystem paths from strings for logging or display.

    Specifically replaces user-specific or machine-specific paths with
    generic placeholders to avoid leaking information such as usernames,
    home directories, or working directories.

    Redacted locations (if applicable and present in the input):
      - User's home directory → "<Redacted:HOME>"
      - Current working directory → "<Redacted:CWD>"
      - System temporary directory → "<Redacted:TMP>"

    All paths are resolved and normalized to ensure platform independence
    and avoid false matches due to symlinks, casing, or path style differences.

    Attributes:
        HOMEDIR (str): Canonical absolute path to the user's home directory.
        CWD (str): Canonical absolute path to the current working directory.
        TMP (str): Canonical absolute path to the temporary directory.
    """

    def __init__(self, redactions: Mapping[str, str] | None = None) -> None:
        """Initialize a PathRedactor with optional custom redaction mappings.

        Args:
            redactions: An optional mapping of absolute paths to placeholder
                labels. If not provided, default mappings for the user's home
                directory, current working directory, and system temporary
                directory are used.
        """
        self.redactions = redactions or self._default_redactions

    @cached_property
    def _default_redactions(self) -> dict[str, str]:
        """Compute default redaction mappings for sensitive system paths.

        Returns:
            A dictionary mapping absolute paths to placeholder labels
            (e.g., $HOME, $CWD, $TMP).
        """
        os = import_lazy("os")
        path = os.path
        tempfile = import_lazy("tempfile")

        homedir = path.normcase(path.abspath(path.expanduser("~")))
        cwd = path.normcase(path.realpath(os.getcwd()))
        tmp = path.normcase(tempfile.gettempdir())

        return {
            homedir: "$HOME",
            cwd: "$CWD",
            tmp: "$TMP",
        }

    @override
    def redact(self, data: str) -> str:
        """Redacts sensitive path prefixes from the given path.

        Args:
            data: The file path to sanitize.

        Returns:
            The path with known sensitive prefixes replaced by placeholders.
        """
        path = import_lazy("os.path")
        norm_path = path.normcase(path.realpath(data))
        for base, label in self.redactions.items():
            base_norm = path.normcase(base)
            if (
                norm_path.startswith(base_norm + path.sep)
                or norm_path == base_norm
            ):
                return data.replace(base, label)

        return data


class UnionRedactor(BaseRedactor):
    """Composable redactor that applies multiple redactors in sequence.

    Each redactor is applied in order to the result of the previous one.
    Use this to combine multiple string transformations into a single pass.
    """

    __slots__ = ("redactors",)

    def __init__(self, redactors: Iterable[BaseRedactor]) -> None:
        """Initialize a UnionRedactor from a sequence of redactors.

        Args:
            redactors: Iterable of functions each taking and returning a
            string.
        """
        self.redactors = tuple(redactors)

    def redact(self, data: str) -> str:
        """Redact the input string using all composed redactors.

        Args:
            data: The string to redact.

        Returns:
            The final redacted string after applying all redactors.
        """
        for redactor in self.redactors:
            data = redactor(data)

        return data


@cache
def _email_pattern() -> Callable[[str, str], str]:
    """Return a callable that replaces email addresses.

    Returns:
        A function: (replacement, input_string) -> redacted string.
    """
    return (
        import_lazy("re")
        .compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
        .sub
    )


class EmailRedactor(BaseRedactor):
    """Redactor that replaces email addresses with a placeholder."""

    __slots__ = ()

    @override
    def redact(self, data: str) -> str:
        return _email_pattern()("<Redacted:EMAIL>", data)


@cache
def _ip_pattern() -> Callable[[str, str], str]:
    """Return a callable that replaces IPv4 addresses.

    Returns:
        A function: (replacement, input_string) -> redacted string.
    """
    return import_lazy("re").compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b").sub


class IPRedactor(BaseRedactor):
    """Redactor that replaces IPv4 addresses with a placeholder."""

    __slots__ = ()

    @override
    def redact(self, data: str) -> str:
        return _ip_pattern()("<Redacted:IP>", data)


@cache
def _mac_pattern() -> Callable[[str, str], str]:
    """Return a callable that replaces MAC addresses.

    Returns:
        A function: (replacement, input_string) -> redacted string.
    """
    return (
        import_lazy("re")
        .compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
        .sub
    )


class MACRedactor(BaseRedactor):
    """Redacts MAC addresses (e.g., 00:1A:2B:3C:4D:5E) from strings."""

    __slots__ = ()

    @override
    def redact(self, data: str) -> str:
        return _mac_pattern()("<Redacted:MAC>", data)
