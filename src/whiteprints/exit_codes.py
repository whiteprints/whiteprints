# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Comprehensive, typed exit code definitions for CLI and daemon processes.

This module provides:

  - A fully typed `ExitCode` class representing POSIX, Linux-specific, and
    signal-derived exit statuses.
  - Exhaustive symbolic-to-integer and integer-to-symbolic mappings via
    `RAW_EXITCODES`, `REVERSE_EXITCODES`, and `RICH_EXITCODES`.
  - Localizable, human-readable descriptions and standardized symbolic labels
    (e.g., EX_USAGE, EX_SOFTWARE) for integration with translatable messaging.
  - Deterministic and thread-safe exit-time callback registration via
    `ExitCode.atexit()`, designed to operate safely in multithreaded or
    multiprocess environments.
  - Runtime utilities to resolve `ExitCode` instances from raw integers,
    signals, or symbolic names.
  - Atomic execution of exit-time handlers with SIGINT/SIGTERM temporarily
    delayed to ensure safe and complete shutdown.

This implementation avoids `enum.Enum` to reduce import-time overhead and
runtime cost. All mappings are resolved lazily and operate in constant time.

It is suitable for high-performance command-line applications, service
runners, and infrastructure tooling requiring strict control over process
termination semantics.
"""

from collections.abc import Callable
from logging import Logger
from typing import TYPE_CHECKING, Final, Literal, NoReturn, Self

from whiteprints.concurrency import is_main_process, is_main_thread
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_lazy
from whiteprints.signals_handler import DelaySignals


__all__: Final = [
    "RAW_EXITCODES",
    "REVERSE_EXITCODES",
    "RICH_EXITCODES",
    "ExitCode",
    "ExitCodeName",
    "ExitCodeValue",
    "from_signal",
    "from_value",
    "name_of",
]
"""Public module attributes."""


type ExitCodeName = Literal[
    "ADDRESSEE_UNKNOWN",
    "CANNOT_CREATE",
    "CANNOT_OPEN_INPUT",
    "COMMAND_CANNOT_EXECUTE",
    "COMMAND_LINE_USAGE_ERROR",
    "COMMAND_NOT_FOUND",
    "CONFIGURATION_ERROR",
    "CRITICAL_OS_FILE_MISSING",
    "DATA_FORMAT_ERROR",
    "FAILURE",
    "FATAL_SIGNAL_BASE",
    "HOST_NAME_UNKNOWN",
    "INTERNAL_SOFTWARE_ERROR",
    "INVALID_ARGUMENT",
    "IO_ERROR",
    "MISUSE_OF_SHELL_BUILTINS",
    "PERMISSION_DENIED",
    "REMOTE_PROTOCOL_ERROR",
    "SERVICE_UNAVAILABLE",
    "SIG_ABRT",
    "SIG_ALRM",
    "SIG_BUS",
    "SIG_CHLD",
    "SIG_CONT",
    "SIG_FPE",
    "SIG_HUP",
    "SIG_ILL",
    "SIG_INT",
    "SIG_KILL",
    "SIG_PIPE",
    "SIG_POLL",
    "SIG_PROF",
    "SIG_PWR",
    "SIG_QUIT",
    "SIG_SEGV",
    "SIG_STKFLT",
    "SIG_STOP",
    "SIG_SYS",
    "SIG_TERM",
    "SIG_TRAP",
    "SIG_TSTP",
    "SIG_TTIN",
    "SIG_TTOU",
    "SIG_URG",
    "SIG_USR1",
    "SIG_USR2",
    "SIG_VTALRM",
    "SIG_WINCH",
    "SIG_XCPU",
    "SIG_XFSZ",
    "STATUS_OUT_OF_RANGE",
    "SUCCESS",
    "SYSTEM_ERROR",
    "TEMPORARY_FAILURE",
    "TIMEOUT",
    "TIMEOUT_CANCELED",
]
"""Symbolic name of a POSIX or Linux exit code."""

type ExitCodeValue = Literal[
    0,
    1,
    2,
    3,
    64,
    65,
    66,
    67,
    68,
    69,
    70,
    71,
    72,
    73,
    74,
    75,
    76,
    77,
    78,
    124,
    125,
    126,
    127,
    128,
    129,
    130,
    131,
    132,
    133,
    134,
    135,
    136,
    137,
    138,
    139,
    140,
    141,
    142,
    143,
    144,
    145,
    146,
    147,
    148,
    149,
    150,
    151,
    152,
    153,
    154,
    155,
    156,
    157,
    158,
    159,
    255,
]
"""Integer value of a known exit code, conforming to POSIX or Linux."""


RAW_EXITCODES: Final[dict[ExitCodeName, ExitCodeValue]] = {
    "SUCCESS": 0,
    "FAILURE": 1,
    "MISUSE_OF_SHELL_BUILTINS": 2,
    "INVALID_ARGUMENT": 3,
    "COMMAND_LINE_USAGE_ERROR": 64,
    "DATA_FORMAT_ERROR": 65,
    "CANNOT_OPEN_INPUT": 66,
    "ADDRESSEE_UNKNOWN": 67,
    "HOST_NAME_UNKNOWN": 68,
    "SERVICE_UNAVAILABLE": 69,
    "INTERNAL_SOFTWARE_ERROR": 70,
    "SYSTEM_ERROR": 71,
    "CRITICAL_OS_FILE_MISSING": 72,
    "CANNOT_CREATE": 73,
    "IO_ERROR": 74,
    "TEMPORARY_FAILURE": 75,
    "REMOTE_PROTOCOL_ERROR": 76,
    "PERMISSION_DENIED": 77,
    "CONFIGURATION_ERROR": 78,
    "TIMEOUT": 124,
    "TIMEOUT_CANCELED": 125,
    "COMMAND_CANNOT_EXECUTE": 126,
    "COMMAND_NOT_FOUND": 127,
    "FATAL_SIGNAL_BASE": 128,
    "SIG_HUP": 129,
    "SIG_INT": 130,
    "SIG_QUIT": 131,
    "SIG_ILL": 132,
    "SIG_TRAP": 133,
    "SIG_ABRT": 134,
    "SIG_BUS": 135,
    "SIG_FPE": 136,
    "SIG_KILL": 137,
    "SIG_USR1": 138,
    "SIG_SEGV": 139,
    "SIG_USR2": 140,
    "SIG_PIPE": 141,
    "SIG_ALRM": 142,
    "SIG_TERM": 143,
    "SIG_STKFLT": 144,
    "SIG_CHLD": 145,
    "SIG_CONT": 146,
    "SIG_STOP": 147,
    "SIG_TSTP": 148,
    "SIG_TTIN": 149,
    "SIG_TTOU": 150,
    "SIG_URG": 151,
    "SIG_XCPU": 152,
    "SIG_XFSZ": 153,
    "SIG_VTALRM": 154,
    "SIG_PROF": 155,
    "SIG_WINCH": 156,
    "SIG_POLL": 157,
    "SIG_PWR": 158,
    "SIG_SYS": 159,
    "STATUS_OUT_OF_RANGE": 255,
}
"""Mapping from symbolic exit code names to their raw integer values."""


class ExitCode(int):
    """POSIX, Linux, and signal-based exit status code.

    `ExitCode` is an integer subclass enriched with metadata and lifecycle
    management. It supports symbolic lookup, formatted descriptions, and
    graceful shutdown logic via exit-time handler registration.

    Handlers registered through `ExitCode.atexit()` are:

      - Executed exactly once, in deterministic order.
      - Run before interpreter finalization.
      - Protected from SIGINT and SIGTERM by temporary signal masking.

    This ensures clean, atomic teardown even under keyboard interrupts or
    external termination requests.

    Attributes:
        description: Exit code description.
        standard_name: Symbolic or standard name for the code, if any.
    """

    description: str
    standard_name: str | None

    @classmethod
    def atexit(cls, handler: Callable[[], None]) -> None:
        """Register a callable to be executed during controlled program exit.

        This method provides a deterministic and thread-safe mechanism to
        register cleanup callbacks that run before interpreter teardown. It is
        strictly intended for scenarios where all runtime resources (threads,
        queues, pipes, etc.) are still valid and operable.

        Unlike Python's built-in `atexit` module—which may execute after core
        runtime subsystems have been finalized—this method ensures that
        shutdown hooks run while all user-defined infrastructure remains
        intact.

        Handlers are expected to be idempotent, thread-safe, and non-raising.
        No attempt is made to catch exceptions during execution. Failure of a
        handler is considered a critical bug and will propagate as-is.

        It acts as a pre-atexit coordination layer and is suitable for clean
        deallocation of threads, subprocesses, and inter-process primitives.

        Args:
            handler: A zero-argument callable to be invoked during `exit()`.

        Note:
            Internally, handlers are stored in a `dict[Callable, None]` to
            guarantee both:
              - Uniqueness: duplicate registrations of the same callable are
                ignored.
              - Deterministic order: handlers are invoked in the order they
                were registered (insertion order is preserved since Python
                3.7).
        """
        if is_main_thread() and is_main_process():
            print("ATEXIT REGISTER", import_lazy("os").getpid(), handler)
            with DelaySignals():
                import_lazy("atexit").register(handler)

    def __new__(
        cls,
        value: int,
        description: str,
        standard_name: str | None = None,
    ) -> Self:
        """Create a new ExitCode instance.

        Args:
            value: the integer code.
            description: explanation of the code purpose.
            standard_name: optional symbolic name.

        Returns:
            The ExitCode instance.
        """
        with DelaySignals():
            obj = int.__new__(cls, value)
            obj.description = description
            obj.standard_name = standard_name

            return obj

    def log(self, logger: Logger, *, stack_info: bool = False) -> Self:
        """Log the exit code with context.

        Args:
            logger: the logger to use.
            stack_info: whether to include stack trace info.

        Returns:
            Self.
        """
        with DelaySignals():
            logger.debug(
                "Program exited",
                stack_info=stack_info,
                extra={
                    "exit_code": {
                        "value": self,
                        "name": name_of(self),
                        "description": self.description,
                        "standard_name": self.standard_name,
                    }
                },
            )

            return self

    def exit(self, source: BaseException | None = None) -> NoReturn:
        """Terminate the interpreter with this exit code after safe teardown.

        Executes all registered `ExitCode.atexit()` handlers in registration
        order under a `DelaySignals` context to block critical signals such as
        SIGINT and SIGTERM during shutdown. This ensures handlers run
        atomically without asynchronous interruption.

        Handlers are expected to be:

          - Idempotent (may be called multiple times),
          - Thread-safe (may run concurrently with non-daemon threads),
          - Non-raising (any exception will propagate immediately).

        The use of `DelaySignals` guarantees that the shutdown phase is not
        interrupted by asynchronous signals. If a signal is received while
        masked, it will be delivered only after the context exits—i.e., after
        all handlers complete.

        This method should be called before interpreter finalization. Invoking
        it too late (e.g., from `__del__`, `weakref`, or built-in `atexit`) may
        result in undefined behavior.

        Args:
            source: Optional originating exception to chain with SystemExit.

        Raises:
            SystemExit: Unconditionally, to terminate the current process.
        """
        print("SYSTEMEXIT FROM", import_lazy("os").getpid())
        with DelaySignals():
            try:
                raise SystemExit(self) from (
                    source if not isinstance(source, SystemExit) else None
                )
            except KeyboardInterrupt as keyboard_interrupt:
                raise SystemExit(
                    RAW_EXITCODES["SIG_INT"]
                ) from keyboard_interrupt

    def __reduce__(self) -> tuple[type, tuple[int, str, str | None]]:
        """Support for `pickle` serialization of ExitCode.

        This method returns the information needed to reconstruct the ExitCode
        instance during unpickling. It ensures that all important attributes
        (`value`, `description`, `standard_name`) are preserved.

        Returns:
            A tuple containing the class and the constructor arguments.
        """
        with DelaySignals():
            return (
                self.__class__,
                (int(self), self.description, self.standard_name),
            )

    def as_signal(self) -> int | None:
        """Return the signal number if this exit code was caused by a signal.

        POSIX reserves exit codes 129-159 for processes terminated by signals.
        These are defined as `128 + signal_number`.

        Returns:
            The signal number (e.g. 2 for SIGINT) if this code reflects signal
            termination; otherwise, None.
        """
        if RAW_EXITCODES["SIG_HUP"] <= self <= RAW_EXITCODES["SIG_SYS"]:
            return self - 128

        return None


REVERSE_EXITCODES: Final[
    dict[ExitCodeValue | ExitCode | int, ExitCodeName]
] = {
    0: "SUCCESS",
    1: "FAILURE",
    2: "MISUSE_OF_SHELL_BUILTINS",
    3: "INVALID_ARGUMENT",
    64: "COMMAND_LINE_USAGE_ERROR",
    65: "DATA_FORMAT_ERROR",
    66: "CANNOT_OPEN_INPUT",
    67: "ADDRESSEE_UNKNOWN",
    68: "HOST_NAME_UNKNOWN",
    69: "SERVICE_UNAVAILABLE",
    70: "INTERNAL_SOFTWARE_ERROR",
    71: "SYSTEM_ERROR",
    72: "CRITICAL_OS_FILE_MISSING",
    73: "CANNOT_CREATE",
    74: "IO_ERROR",
    75: "TEMPORARY_FAILURE",
    76: "REMOTE_PROTOCOL_ERROR",
    77: "PERMISSION_DENIED",
    78: "CONFIGURATION_ERROR",
    124: "TIMEOUT",
    125: "TIMEOUT_CANCELED",
    126: "COMMAND_CANNOT_EXECUTE",
    127: "COMMAND_NOT_FOUND",
    128: "FATAL_SIGNAL_BASE",
    129: "SIG_HUP",
    130: "SIG_INT",
    131: "SIG_QUIT",
    132: "SIG_ILL",
    133: "SIG_TRAP",
    134: "SIG_ABRT",
    135: "SIG_BUS",
    136: "SIG_FPE",
    137: "SIG_KILL",
    138: "SIG_USR1",
    139: "SIG_SEGV",
    140: "SIG_USR2",
    141: "SIG_PIPE",
    142: "SIG_ALRM",
    143: "SIG_TERM",
    144: "SIG_STKFLT",
    145: "SIG_CHLD",
    146: "SIG_CONT",
    147: "SIG_STOP",
    148: "SIG_TSTP",
    149: "SIG_TTIN",
    150: "SIG_TTOU",
    151: "SIG_URG",
    152: "SIG_XCPU",
    153: "SIG_XFSZ",
    154: "SIG_VTALRM",
    155: "SIG_PROF",
    156: "SIG_WINCH",
    157: "SIG_POLL",
    158: "SIG_PWR",
    159: "SIG_SYS",
    255: "STATUS_OUT_OF_RANGE",
}
"""Reverse mapping from integer values to their symbolic exit code names."""

RICH_EXITCODES: Final = {
    0: lambda: (_("Successful termination."), "SUCCESS"),
    1: lambda: (_("Catchall for general errors."), "FAILURE"),
    2: lambda: (_("Misuse of shell builtins."), None),
    3: lambda: (_("Miscellaneous invalid argument."), None),
    64: lambda: (_("Command line usage error."), "EX_USAGE"),
    65: lambda: (_("Data format error."), "EX_DATAERR"),
    66: lambda: (_("Cannot open input."), "EX_NOINPUT"),
    67: lambda: (_("Addressee unknown."), "EX_NOUSER"),
    68: lambda: (_("Host name unknown."), "EX_NOHOST"),
    69: lambda: (_("Service unavailable."), "EX_UNAVAILABLE"),
    70: lambda: (_("Internal software error."), "EX_SOFTWARE"),
    71: lambda: (_("System error."), "EX_OSERR"),
    72: lambda: (_("Critical OS file missing."), "EX_OSFILE"),
    73: lambda: (_("Cannot create output file."), "EX_CANTCREAT"),
    74: lambda: (_("Input/output error."), "EX_IOERR"),
    75: lambda: (_("Temporary failure."), "EX_TEMPFAIL"),
    76: lambda: (_("Remote protocol error."), "EX_PROTOCOL"),
    77: lambda: (_("Permission denied."), "EX_NOPERM"),
    78: lambda: (_("Configuration error."), "EX_CONFIG"),
    124: lambda: (_("Command timed out."), "EXIT_TIMEOUT"),
    125: lambda: (
        _("Timeout command failed to execute or was canceled."),
        "CANCELED",
    ),
    126: lambda: (_("Command invoked cannot execute."), None),
    127: lambda: (_("Command not found."), None),
    128: lambda: (
        _("Base exit code for fatal signals (128 + signal number)."),
        None,
    ),
    129: lambda: (_("Hangup detected on controlling terminal."), "SIG_HUP"),
    130: lambda: (_("Interrupt from keyboard."), "SIG_INT"),
    131: lambda: (_("Quit from keyboard."), "SIG_QUIT"),
    132: lambda: (_("Illegal instruction."), "SIG_ILL"),
    133: lambda: (_("Trace/breakpoint trap."), "SIG_TRAP"),
    134: lambda: (_("Abort signal from abort(3)."), "SIG_ABRT"),
    135: lambda: (_("Bus error."), "SIG_BUS"),
    136: lambda: (_("Floating point exception."), "SIG_FPE"),
    137: lambda: (_("Kill signal."), "SIG_KILL"),
    138: lambda: (_("User-defined signal 1."), "SIG_USR1"),
    139: lambda: (_("Segmentation fault."), "SIG_SEGV"),
    140: lambda: (_("User-defined signal 2."), "SIG_USR2"),
    141: lambda: (_("Broken pipe."), "SIG_PIPE"),
    142: lambda: (_("Timer signal."), "SIG_ALRM"),
    143: lambda: (_("Termination signal."), "SIG_TERM"),
    144: lambda: (_("Stack fault."), "SIG_STKFLT"),
    145: lambda: (_("Child stopped or terminated."), "SIG_CHLD"),
    146: lambda: (_("Continue if stopped."), "SIG_CONT"),
    147: lambda: (_("Stop process."), "SIG_STOP"),
    148: lambda: (_("Stop typed at terminal."), "SIG_TSTP"),
    149: lambda: (_("Terminal input for background process."), "SIG_TTIN"),
    150: lambda: (_("Terminal output for background process."), "SIG_TTOU"),
    151: lambda: (_("Urgent condition on socket."), "SIG_URG"),
    152: lambda: (_("CPU time limit exceeded."), "SIG_XCPU"),
    153: lambda: (_("File size limit exceeded."), "SIG_XFSZ"),
    154: lambda: (_("Virtual alarm clock."), "SIG_VTALRM"),
    155: lambda: (_("Profiling timer expired."), "SIG_PROF"),
    156: lambda: (_("Window resize signal."), "SIG_WINCH"),
    157: lambda: (_("Pollable event."), "SIG_POLL"),
    158: lambda: (_("Power failure."), "SIG_PWR"),
    159: lambda: (_("Bad system call."), "SIG_SYS"),
    255: lambda: (_("Exit status out of range (greater than 255)."), None),
}
"""Mapping from exit code integers to a lazy (description, alias) pair."""


def _make_exitcode(name: ExitCodeName) -> ExitCode:
    """Create and cache an ExitCode instance.

    Args:
        name: exit code name.

    Returns:
        A lazily constructed ExitCode object.
    """
    val = RAW_EXITCODES[name]
    desc, std = RICH_EXITCODES[val]()
    return ExitCode(val, desc, std)


def __getattr__(name: ExitCodeName | str) -> ExitCode:
    if name in RAW_EXITCODES:
        return _make_exitcode(name)

    raise AttributeError(name)


def name_of(code: ExitCode | ExitCodeValue | int) -> ExitCodeName:
    """Get the symbolic name for an ExitCode instance.

    Args:
        code: ExitCode instance.

    Returns:
        Symbolic name.
    """
    return REVERSE_EXITCODES[code]


def from_signal(signal_number: ExitCodeValue | int) -> ExitCode:
    """Resolve an exit code from a signal number.

    Args:
        signal_number: POSIX signal number.

    Returns:
        ExitCode instance.
    """
    return __getattr__(REVERSE_EXITCODES[128 + signal_number])


def from_value(value: ExitCodeValue) -> ExitCode:
    """Resolve an exit code from a raw integer value.

    Args:
        value: Integer exit code (modulo 256).

    Returns:
        ExitCode instance.
    """
    return __getattr__(REVERSE_EXITCODES[value % 256])


if TYPE_CHECKING:
    SUCCESS: ExitCode
    FAILURE: ExitCode
    MISUSE_OF_SHELL_BUILTINS: ExitCode
    INVALID_ARGUMENT: ExitCode
    COMMAND_LINE_USAGE_ERROR: ExitCode
    DATA_FORMAT_ERROR: ExitCode
    CANNOT_OPEN_INPUT: ExitCode
    ADDRESSEE_UNKNOWN: ExitCode
    HOST_NAME_UNKNOWN: ExitCode
    SERVICE_UNAVAILABLE: ExitCode
    INTERNAL_SOFTWARE_ERROR: ExitCode
    SYSTEM_ERROR: ExitCode
    CRITICAL_OS_FILE_MISSING: ExitCode
    CANNOT_CREATE: ExitCode
    IO_ERROR: ExitCode
    TEMPORARY_FAILURE: ExitCode
    REMOTE_PROTOCOL_ERROR: ExitCode
    PERMISSION_DENIED: ExitCode
    CONFIGURATION_ERROR: ExitCode
    TIMEOUT: ExitCode
    TIMEOUT_CANCELED: ExitCode
    COMMAND_CANNOT_EXECUTE: ExitCode
    COMMAND_NOT_FOUND: ExitCode
    FATAL_SIGNAL_BASE: ExitCode
    SIG_HUP: ExitCode
    SIG_INT: ExitCode
    SIG_QUIT: ExitCode
    SIG_ILL: ExitCode
    SIG_TRAP: ExitCode
    SIG_ABRT: ExitCode
    SIG_BUS: ExitCode
    SIG_FPE: ExitCode
    SIG_KILL: ExitCode
    SIG_USR1: ExitCode
    SIG_SEGV: ExitCode
    SIG_USR2: ExitCode
    SIG_PIPE: ExitCode
    SIG_ALRM: ExitCode
    SIG_TERM: ExitCode
    SIG_STKFLT: ExitCode
    SIG_CHLD: ExitCode
    SIG_CONT: ExitCode
    SIG_STOP: ExitCode
    SIG_TSTP: ExitCode
    SIG_TTIN: ExitCode
    SIG_TTOU: ExitCode
    SIG_URG: ExitCode
    SIG_XCPU: ExitCode
    SIG_XFSZ: ExitCode
    SIG_VTALRM: ExitCode
    SIG_PROF: ExitCode
    SIG_WINCH: ExitCode
    SIG_POLL: ExitCode
    SIG_PWR: ExitCode
    SIG_SYS: ExitCode
    STATUS_OUT_OF_RANGE: ExitCode
