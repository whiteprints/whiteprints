# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Everything related to the command line interface."""

import gettext
import importlib
from collections.abc import Callable
from types import FrameType, SimpleNamespace
from typing import Final, NoReturn

from whiteprints import _, has_extra, import_extra


__all__: Final = [
    "ExitCode",
    "PosixExitCode",
    "robust_print",
    "robust_print_json",
]
"""Public module attributes."""


robust_print = print if (rich := import_extra("rich")) is None else rich.print


class ExitCode(int):
    """POSIX, Linux, and signal-based exit status codes.

    Includes:
        - Shell-reserved statuses (0-2, 126-255)
        - BSD/GNU `sysexits.h` codes (64-78)
        - Signal-based terminations (128+SIGNAL)
    """

    def exit(self, source: Exception | None = None) -> NoReturn:
        """Exit with a given posix exit code.

        Raises:
            SystemExit: exit the programe with the enum exit code.
        """
        raise SystemExit(self) from source


class PosixExitCode(SimpleNamespace):
    """POSIX, Linux, and signal-based exit status codes.

    Includes:
        - Shell-reserved statuses (0-2, 126-255)
        - BSD/GNU `sysexits.h` codes (64-78)
        - Signal-based terminations (128+SIGNAL)
    """

    SUCCESS = ExitCode(0)
    """Successful termination."""
    GENERAL_ERROR = ExitCode(1)
    """Catchall for general errors."""
    MISUSE_OF_SHELL_BUILTINS = ExitCode(2)
    """Misuse of shell builtins."""
    INVALID_ARGUMENT = ExitCode(3)
    """Miscellaneous invalid argument."""
    INPUT_OUTPUT_ERROR = ExitCode(5)
    """Input/output error (alternate)."""
    NO_SUCH_DEVICE_OR_ADDRESS = ExitCode(6)
    """No such device or address."""

    # BSD/GNU "sysexits.h" codes
    COMMAND_LINE_USAGE_ERROR = ExitCode(64)
    """Command line usage error (sysexits.h EX_USAGE)."""
    DATA_FORMAT_ERROR = ExitCode(65)
    """Data format error (sysexits.h EX_DATAERR)."""
    CANNOT_OPEN_INPUT = ExitCode(66)
    """Cannot open input (sysexits.h EX_NOINPUT)."""
    ADDRESSEE_UNKNOWN = ExitCode(67)
    """Addressee unknown (sysexits.h EX_NOUSER)."""
    HOST_NAME_UNKNOWN = ExitCode(68)
    """Host name unknown (sysexits.h EX_NOHOST)."""
    SERVICE_UNAVAILABLE = ExitCode(69)
    """Service unavailable (sysexits.h EX_UNAVAILABLE)."""
    INTERNAL_SOFTWARE_ERROR = ExitCode(70)
    """Internal software error (sysexits.h EX_SOFTWARE)."""
    SYSTEM_ERROR = ExitCode(71)
    """System error (sysexits.h EX_OSERR)."""
    CRITICAL_OS_FILE_MISSING = ExitCode(72)
    """Critical OS file missing (sysexits.h EX_OSFILE)."""
    CANNOT_CREATE = ExitCode(73)
    """Cannot create output file (sysexits.h EX_CANTCREAT)."""
    IO_ERROR = ExitCode(74)
    """Input/output error (sysexits.h EX_IOERR)."""
    TEMPORARY_FAILURE = ExitCode(75)
    """Temporary failure (sysexits.h EX_TEMPFAIL)."""
    REMOTE_PROTOCOL_ERROR = ExitCode(76)
    """Remote protocol error (sysexits.h EX_PROTOCOL)."""
    PERMISSION_DENIED = ExitCode(77)
    """Permission denied (sysexits.h EX_NOPERM)."""
    CONFIGURATION_ERROR = ExitCode(78)
    """Configuration error (sysexits.h EX_CONFIG)."""

    # Commands and invalid exit argument
    COMMAND_CANNOT_EXECUTE = ExitCode(126)
    """Command invoked cannot execute."""
    COMMAND_NOT_FOUND = ExitCode(127)
    """Command not found."""
    INVALID_EXIT_ARGUMENT = ExitCode(128)
    """Invalid argument to exit."""

    # Signal-based exit codes
    EXIT_SIG_HUP = ExitCode(129)
    """Hangup detected on controlling terminal (SIGHUP)."""
    EXIT_SIG_INT = ExitCode(130)
    """Interrupt from keyboard (SIGINT)."""
    EXIT_SIG_QUIT = ExitCode(131)
    """Quit from keyboard (SIGQUIT)."""
    EXIT_SIG_ILL = ExitCode(132)
    """Illegal instruction (SIGILL)."""
    EXIT_SIG_TRAP = ExitCode(133)
    """Trace/breakpoint trap (SIGTRAP)."""
    EXIT_SIG_ABRT = ExitCode(134)
    """Abort signal from abort(3) (SIGABRT)."""
    EXIT_SIG_BUS = ExitCode(135)
    """Bus error (SIGBUS)."""
    EXIT_SIG_FPE = ExitCode(136)
    """Floating point exception (SIGFPE)."""
    EXIT_SIG_KILL = ExitCode(137)
    """Kill signal (SIGKILL)."""
    EXIT_SIG_USR1 = ExitCode(138)
    """User-defined signal 1 (SIGUSR1)."""
    EXIT_SIG_SEGV = ExitCode(139)
    """Segmentation fault (SIGSEGV)."""
    EXIT_SIG_USR2 = ExitCode(140)
    """User-defined signal 2 (SIGUSR2)."""
    EXIT_SIG_PIPE = ExitCode(141)
    """Broken pipe (SIGPIPE)."""
    EXIT_SIG_ALRM = ExitCode(142)
    """Timer signal (SIGALRM)."""
    EXIT_SIG_TERM = ExitCode(143)
    """Termination signal (SIGTERM)."""
    EXIT_SIG_STKFLT = ExitCode(144)
    """Stack fault (SIGSTKFLT)."""
    EXIT_SIG_CHLD = ExitCode(145)
    """Child stopped or terminated (SIGCHLD)."""
    EXIT_SIG_CONT = ExitCode(146)
    """Continue if stopped (SIGCONT)."""
    EXIT_SIG_STOP = ExitCode(147)
    """Stop process (SIGSTOP)."""
    EXIT_SIG_TSTP = ExitCode(148)
    """Stop typed at terminal (SIGTSTP)."""
    EXIT_SIG_TTIN = ExitCode(149)
    """Terminal input for background process (SIGTTIN)."""
    EXIT_SIG_TTOU = ExitCode(150)
    """Terminal output for background process (SIGTTOU)."""
    EXIT_SIG_URG = ExitCode(151)
    """Urgent condition on socket (SIGURG)."""
    EXIT_SIG_XCPU = ExitCode(152)
    """CPU time limit exceeded (SIGXCPU)."""
    EXIT_SIG_XFSZ = ExitCode(153)
    """File size limit exceeded (SIGXFSZ)."""
    EXIT_SIG_VTALRM = ExitCode(154)
    """Virtual alarm clock (SIGVTALRM)."""
    EXIT_SIG_PROF = ExitCode(155)
    """Profiling timer expired (SIGPROF)."""
    EXIT_SIG_WINCH = ExitCode(156)
    """Window resize signal (SIGWINCH)."""
    EXIT_SIG_POLL = ExitCode(157)
    """Pollable event (SIGIO)."""
    EXIT_SIG_PWR = ExitCode(158)
    """Power failure (SIGPWR)."""
    EXIT_SIG_SYS = ExitCode(159)
    """Bad system call (SIGSYS)."""

    # Invalid exit status
    EXIT_STATUS_OUT_OF_RANGE = ExitCode(255)
    """Exit status out of range (greater than 255)."""

    @classmethod
    def from_signal(cls, signal_number: int) -> ExitCode:
        """Create a posix exit code from a signal number.

        The posix exit code is obtained by adding 128 to the signal number.

        Returns:
            A PosixExitCode corresponding to the given Python signal.
        """
        return ExitCode(128 + signal_number)


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
