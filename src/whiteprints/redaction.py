# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Safe string wrappers with redaction and secret handling.

This module provides three classes to represent strings with different levels
of visibility and redaction:

- `Secret`: A fully redacted string whose original value is replaced with a
  key, and the original is hidden.
- `Sensitive`: A partially redacted string that replaces sensitive parts with
  placeholders while keeping the rest visible.
- `Clear`: A plain string with no redaction.

These are useful for structured logging, debugging, or any context where data
should be controlled without removing traceability.
"""

from typing import Final, Self, TypedDict

from whiteprints.logs.lazy_logrecord_value import LazyRecordValue
from whiteprints.redactor import BaseRedactor


__all__: Final = [
    "Clear",
    "SafeString",
    "Secret",
    "Sensitive",
    "safe_string_json_redacted",
    "safe_string_json_revealed",
]
"""Public module attributes."""


def safe_string_json_redacted(obj: object) -> object:
    """Serialize a SafeString object to its redacted representation.

    Args:
        obj: The object to serialize.

    Returns:
        The redacted string if obj is a SafeString, else str(obj).
    """
    if isinstance(obj, SafeString):
        return obj.redact

    return str(obj)


def safe_string_json_revealed(obj: object) -> object:
    """Serialize a SafeString object to its revealed/original representation.

    Args:
        obj: The object to serialize.

    Returns:
        The original string if obj is a SafeString, else str(obj).
    """
    if isinstance(obj, SafeString):
        return obj.reveal

    return str(obj)


class SafeString:
    """Base class for redacted or safe string representations.

    Subclasses must implement `reveal` and `redacted` properties to handle
    string visibility logic.
    """

    __slots__ = ("data", "origin", "redacted")

    def __init__(
        self, data: str, redacted: str, origin: str | Self | None = None
    ) -> None:
        """Initialize a SafeString instance.

        Args:
            data: The original string data.
            redacted: The redacted representation of the string.
            origin: The origin or source of the string.
        """
        self.data = data
        self.redacted = redacted
        self.origin = origin

    @property
    def reveal(self) -> str:
        """Reveal the unredacted/original value of the string.

        Returns:
            the original data.
        """
        return self.data

    @property
    def redact(self) -> str:
        """Return the redacted string representation.

        Returns:
            The redacted string.
        """
        return f"<{self.__class__.__name__}:{self.redacted!r}>"

    def __repr__(self) -> str:
        """Return the official string representation of the object.

        Returns:
            The redacted string representation.
        """
        return f"{self.redact}"

    def __str__(self) -> str:
        """Return the informal string representation.

        Returns:
            The redacted string representation.
        """
        return self.redact

    def __eq__(self, other: object) -> bool:
        """Compare equality with another object.

        Args:
            other: Another SafeString or str to compare.

        Returns:
            True if underlying data matches, else False.

        Raises:
            NotImplementedError: If comparison with unsupported type.
        """
        if isinstance(other, SafeString):
            return self.data == other.data

        if isinstance(other, str):
            return self.data == other

        raise NotImplementedError

    def __hash__(self) -> int:
        """Return the hash of the string data.

        Returns:
            Hash value of the original data.
        """
        return hash(self.data)

    def __len__(self) -> int:
        """Return the length of the original string data.

        Returns:
            Length of the original data.
        """
        return len(self.data)

    def __contains__(self, item: object) -> bool:
        """Check if an item is contained in the original string data.

        Args:
            item: A string or SafeString to check for containment.

        Returns:
            True if contained, False otherwise.

        Raises:
            NotImplementedError: If item type is unsupported.
        """
        if isinstance(item, str):
            return item in self.data

        if isinstance(item, type(self)):
            return item.reveal in self.data

        raise NotImplementedError

    def __bool__(self) -> bool:
        """Return the boolean value of the string data.

        Returns:
            True if data is non-empty, False otherwise.
        """
        return bool(self.data)

    def __getitem__(self, key: int | slice) -> str:
        """Retrieve a slice or character from the original string data.

        Args:
            key: Index or slice object.

        Returns:
            Substring or character at the given position.
        """
        return self.data[key]


class Secret(SafeString):
    """A fully redacted string.

    It hides its value and exposes only a label or key.
    """

    __slots__ = ()


class SensitiveState(TypedDict):
    data: str
    origin: str | SafeString | None
    redacted: str
    redactor: LazyRecordValue[str]


class Sensitive(SafeString):
    """A partially redacted string that masks only sensitive portions."""

    __slots__ = ("redactor",)

    def __init__(
        self,
        data: str,
        redactor: BaseRedactor,
        origin: str | SafeString | None = None,
    ) -> None:
        """Initialize a Sensitive string instance with partial redaction.

        Args:
            data: The original string data.
            redactor: A callable that applies redaction to the data.
            origin: The origin or source of the string.
        """
        self.data = data
        self.redactor = redactor
        self.origin = origin

        self.redacted = self.redactor(self.data)


class Clear(SafeString):
    """A plain string that exposes its content without redaction."""

    __slots__ = ()

    def __init__(
        self, data: str, origin: str | SafeString | None = None
    ) -> None:
        """Initialize a Clear string instance without any redaction.

        Args:
            data: The original string data.
            origin: The origin or source of the string.
        """
        self.data = data
        self.redacted = data
        self.origin = origin
