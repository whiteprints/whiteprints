# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Everything related to the command line interface."""

import gettext
import importlib
from collections.abc import Callable
from enum import IntEnum, unique
from types import FrameType
from typing import Final, NoReturn, Self

from whiteprints import _, has_extra, import_extra


__all__: Final = ["robust_print", "robust_print_json"]
"""Public module attributes."""


robust_print = print if (rich := import_extra("rich")) is None else rich.print


@unique
class PosixExitCode(IntEnum):
    """POSIX, Linux, and signal-based exit status codes.

    Includes:
        - Shell-reserved statuses (0-2, 126-255)
        - BSD/GNU `sysexits.h` codes (64-78)
        - Signal-based terminations (128+SIGNAL)
    """

    # Shell-reserved statuses
    SUCCESS = 0
    """Successful termination."""
    GENERAL_ERROR = 1
    """Catchall for general errors."""
    MISUSE_OF_SHELL_BUILTINS = 2
    """Misuse of shell builtins."""
    INVALID_ARGUMENT = 3
    """Miscellaneous invalid argument."""
    INPUT_OUTPUT_ERROR = 5
    """Input/output error (alternate)."""
    NO_SUCH_DEVICE_OR_ADDRESS = 6
    """No such device or address."""

    # BSD/GNU "sysexits.h" codes
    COMMAND_LINE_USAGE_ERROR = 64
    """Command line usage error (sysexits.h EX_USAGE)."""
    DATA_FORMAT_ERROR = 65
    """Data format error (sysexits.h EX_DATAERR)."""
    CANNOT_OPEN_INPUT = 66
    """Cannot open input (sysexits.h EX_NOINPUT)."""
    ADDRESSEE_UNKNOWN = 67
    """Addressee unknown (sysexits.h EX_NOUSER)."""
    HOST_NAME_UNKNOWN = 68
    """Host name unknown (sysexits.h EX_NOHOST)."""
    SERVICE_UNAVAILABLE = 69
    """Service unavailable (sysexits.h EX_UNAVAILABLE)."""
    INTERNAL_SOFTWARE_ERROR = 70
    """Internal software error (sysexits.h EX_SOFTWARE)."""
    SYSTEM_ERROR = 71
    """System error (sysexits.h EX_OSERR)."""
    CRITICAL_OS_FILE_MISSING = 72
    """Critical OS file missing (sysexits.h EX_OSFILE)."""
    CANNOT_CREATE = 73
    """Cannot create output file (sysexits.h EX_CANTCREAT)."""
    IO_ERROR = 74
    """Input/output error (sysexits.h EX_IOERR)."""
    TEMPORARY_FAILURE = 75
    """Temporary failure (sysexits.h EX_TEMPFAIL)."""
    REMOTE_PROTOCOL_ERROR = 76
    """Remote protocol error (sysexits.h EX_PROTOCOL)."""
    PERMISSION_DENIED = 77
    """Permission denied (sysexits.h EX_NOPERM)."""
    CONFIGURATION_ERROR = 78
    """Configuration error (sysexits.h EX_CONFIG)."""

    # Commands and invalid exit argument
    COMMAND_CANNOT_EXECUTE = 126
    """Command invoked cannot execute."""
    COMMAND_NOT_FOUND = 127
    """Command not found."""
    INVALID_EXIT_ARGUMENT = 128
    """Invalid argument to exit."""

    # Signal-based exit codes (auto-generated)
    for signal in importlib.import_module("signal").Signals:
        locals()[f"EXIT_SIG_{signal.name}"] = 128 + signal.value

    EXIT_STATUS_OUT_OF_RANGE = 255
    """Exit status out of range (greater than 255)."""

    def exit(self) -> NoReturn:
        """Exit with a given posix exit code.

        Raises:
            SystemExit: exit the programe with the enum exit code.
        """
        raise SystemExit(self.value)

    @classmethod
    def from_signal(cls, python_signal_number: int) -> Self:
        return cls(128 + python_signal_number)


def robust_print_json(  # noqa: PLR0913
    data: object,
    *,
    indent: int | None = None,
    skip_keys: bool = False,
    ensure_ascii: bool = True,
    check_circular: bool = True,
    allow_nan: bool = False,
    sort_keys: bool = False,
    default: Callable[..., object] | None = None,
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
    if (rich := import_extra("rich")) is None:
        importlib.import_module("json").dump(
            data,
            importlib.import_module("sys").stdout,
            indent=indent,
            skipkeys=skip_keys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            sort_keys=sort_keys,
            default=default,
        )
        importlib.import_module("sys").stdout.write("\n")
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
        f"[red]{error_message}[/]" if has_extra("rich") else error_message,
        file=importlib.import_module("sys").stderr,
    )

    logger = importlib.import_module("logging").getLogger(__name__)
    logger.info(
        "%s received, exiting program.",
        importlib.import_module("signal").Signals(signalnum).name,
        extra={
            "stack": importlib.import_module("traceback").format_stack(frame),
        },
    )
    PosixExitCode.from_signal(signalnum).exit()


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

gettext.bindtextdomain(
    "argparse",
    _.locale_directory,
)
gettext.textdomain("argparse")
