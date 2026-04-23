# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Final


__all__: Final = [
    "WhiteprintsError",
    "format_exception_chain",
]
"""Public module attributes."""


class WhiteprintsError(Exception):
    """A base exception for the Whiteprints project.

    This exception serves as the base class for all errors raised within
    the Whiteprints package. It helps distinguish Whiteprints-specific
    exceptions from others.

    Example:
        >>> class NewError(WhiteprintsError):
        >>>     pass
    """


def _should_include_message(
    idx: int,
    skip: int,
    msg: str | None,
    messages: list[str],
    *,
    nonempty: bool,
) -> bool:
    """Determine if a message should be included in the output.

    Args:
        idx: current position in the exception chain.
        skip: skip first messages.
        nonempty: whether the message is non-empty.
        msg: string representation of the current exception.
        messages: list of already collected messages.

    Returns:
        True if the message is not skipped and not a duplicate; False
        otherwise.
    """
    return idx > skip and nonempty and (not messages or messages[-1] != msg)


def format_exception_chain(
    exc: BaseException,
    cause_message: str = "\n",
    skip: int = 0,
) -> str:
    """Unwraps exception chain and concatenates messages into a single string.

    Args:
        exc: the exception caught.
        cause_message: the execption cause chain message.
        skip: skip first messages.

    Returns:
        a nice error message.
    """
    messages: list[str] = []
    current: BaseException | None = exc
    idx = 1
    while current:
        msg = str(current)
        if _should_include_message(
            idx, skip, msg, messages, nonempty=bool(msg)
        ):
            messages.extend((msg, *getattr(current, "__notes__", ())))

        idx += 1
        current = current.__cause__

    return cause_message.join(messages)
