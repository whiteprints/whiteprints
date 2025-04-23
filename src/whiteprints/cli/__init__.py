# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Everything related to the command line interface."""

import importlib
import sys
from types import FrameType
from typing import Callable, Final, NoReturn, Optional

from whiteprints import _, has_module, maybe_import_module


__all__: Final = ["robust_print", "robust_print_json"]
"""Public module attributes."""


if (rich := maybe_import_module("rich")) is None:
    robust_print = print
else:
    robust_print = rich.print


def robust_print_json(  # noqa: PLR0913
    data: object,
    *,
    indent: Optional[int] = None,
    skip_keys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = False,
    sort_keys: bool = False,
    default: Optional[Callable[..., object]] = None,
) -> None:
    # we disable PLR0913 (too-many-arguments) are we want to mimic json.dump.
    """Try to print a JSON using Rich.

    If rich is not installed use standard Python json.dump with a fallback
    message. If the fallback message is None, then the original message is
    printed.

    Args:
        data: The Python object to be serialized.
        indent: If a positive integer or string, JSON array elements and object
            members will be pretty-printed with that indent level. A positive
            integer indents that many spaces per level. If zero, negative, or
            "" (the empty string), only newlines are inserted. If None (the
            default), the most compact representation is used.
        skip_keys: If True, keys that are not of a basic type (str, int, float,
            bool, None) will be skipped instead of raising a TypeError.
        ensure_ascii: If True (the default), the output is guaranteed to have
            all incoming non-ASCII characters escaped. If False, these
            characters will be outputted as-is.
        check_circular: If False, the circular reference check for container
            types is skipped and a circular reference will result in a
            RecursionError (or worse).
        allow_nan:  If False, serialization of out-of-range float values (nan,
            inf, -inf) will result in a ValueError, in strict compliance with
            the JSON specification. If True (the default), their JavaScript
            equivalents (NaN, Infinity, -Infinity) are used.
        sort_keys: If True, dictionaries will be outputted sorted by key.
        default: A function that is called for objects that can't otherwise be
            serialized. It should return a JSON encodable version of the object
            or raise a TypeError. If None (the default), TypeError is raised.
    """
    if (rich := maybe_import_module("rich")) is None:
        importlib.import_module("json").dump(
            data,
            sys.stdout,
            indent=indent,
            skipkeys=skip_keys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            sort_keys=sort_keys,
            default=default,
        )
        sys.stdout.write("\n")
    else:
        rich.print_json(
            data=data,
            indent=indent,
            skip_keys=skip_keys,
            check_circular=check_circular,
            allow_nan=allow_nan,
            sort_keys=sort_keys,
            default=default,
        )


def _exit_gracefully_action(signalnum: int, frame: FrameType) -> NoReturn:
    """Exit gracefully when a signal is caught.

    The programs exit with the error code being the signal number.

    Args:
        signalnum: the signal number.
        frame: the stack frame.
    """
    error_message = _("Execution stopped by user")
    robust_print(
        f"[red]{error_message}[/]" if has_module("rich") else error_message,
        file=sys.stderr,
    )

    logger = importlib.import_module("logging").getLogger(__name__)
    logger.info(
        "%s received, exiting program.",
        importlib.import_module("signal").Signals(signalnum).name,
        extra={
            "stack": importlib.import_module("traceback").format_stack(frame),
        },
    )
    sys.exit(signalnum)


def _exit_gracefully_on_sigint() -> None:
    """Register a sigint signal handler.

    Example:
        >>> import signal
        >>> import os
        >>>
        >>> _exit_gracefully_on_sigint()
        >>>
        >>> try:
        >>>     os.kill(os.getpid(), signal.SIGINT)
        >>> except SystemExit:
        >>>     print("Bye")
        Bye

    When sigint is caught, the event is logged and the program exits with the
    SIGINT error code.
    """
    signal = importlib.import_module("signal")
    signal.signal(signal.SIGINT, _exit_gracefully_action)


_exit_gracefully_on_sigint()
