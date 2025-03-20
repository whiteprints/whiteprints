# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Top-level module."""

import gettext
import importlib
import sys
from functools import cache
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Final, NoReturn


if TYPE_CHECKING:
    import rich.console


__all__: Final = ["LOCALE_DIRECTORY", "_", "stderr", "stdout"]
"""Public module attributes."""

LOCALE_DIRECTORY: Final = Path(__file__).parent / "locale"
"""Path to the directory containing the locales."""

_: Final = gettext.translation(
    __name__,
    LOCALE_DIRECTORY,
    fallback=True,
).gettext
"""A Gettext translation."""


@cache
def stdout() -> "rich.console.Console":
    """A high level console interface instance.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    See Also:
        https://rich.readthedocs.io/en/stable/reference/console.html

    Example:
        >>> stdout().print("Hello, World!")
        "Hello, World!"

    Returns:
        A rich console printing to the standard output.
    """
    return importlib.import_module("rich.console").Console(soft_wrap=True)


@cache
def stderr() -> "rich.console.Console":
    """A high level console interface instance.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    See Also:
        https://rich.readthedocs.io/en/stable/reference/console.html

    Example:
        >>> stderr().print("Fatal Error!")
        None

    Returns:
        A rich console printing to the standard error.
    """
    return importlib.import_module("rich.console").Console(
        stderr=True, soft_wrap=True
    )


def _exit_gracefully_action(signalnum: int, frame: FrameType) -> NoReturn:
    """Exit gracefully when a signal is caught.

    The programs exit with the error code being the signal number.

    Args:
        signalnum: the signal number.
        frame: the stack frame.
    """
    stderr().print(_("[red]Execution stopped by user[/]"))
    logger = importlib.import_module("logging").getLogger(__name__)
    logger.info(
        "%s received, exiting program.",
        importlib.import_module("signal").Signals(signalnum).name,
        extra={
            "stack": importlib.import_module("traceback").format_stack(frame),
        },
    )
    sys.exit(signalnum)


def exit_gracefully_on_sigint() -> None:
    """Register a sigint signal handler.

    Example:
        >>> import signal
        >>> import os
        >>> exit_gracefully_on_sigint()
        None
        >>> try:
        >>>     os.kill(os.getpid(), signal.SIGINT)
        >>> except SystemExit:
        >>>     print("Bye!")
        "Bye!"

    When sigint is caught, the event is logged and the program exits with the
    SIGINT error code.
    """
    signal = importlib.import_module("signal")
    signal.signal(signal.SIGINT, _exit_gracefully_action)


def _setup_package() -> None:
    """Setup the package.

    Example:
        >>> _setup_package()
        None

    The behaviour of the program is the following:
        * On debug (__debug__ == True), we activate beartype for runtime type
        checking.
        * On release (__debug__ == False), we disable beartype.
    """
    exit_gracefully_on_sigint()

    with importlib.import_module("contextlib").suppress(ModuleNotFoundError):
        importlib.import_module("beartype.claw").beartype_this_package()


_setup_package()
