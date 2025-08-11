# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CLI bootstrap scaffolding.

This module initializes all environment- and signal-related facilities
required for a predictable, fork-safe command-line interface.

Responsibilities:
- Lazily constructs and memoizes the global `ENV` singleton.
- Installs SIGINT and SIGTERM handlers to exit gracefully with structured logs.
- Provides `robust_print` and `robust_print_json` that degrade cleanly
  when `rich` is not installed.
- Localizes argparse (and CLI help strings) via gettext bindings.
- Centralizes exception formatting via `format_exception_chain`.

Design Notes:
- Logging is initialized *after* this module is imported — signal handlers
  rely on the `cli.logs` project but do not themselves emit logging config.
- The `ENV` singleton is deliberately lazy and recreated per process —
  avoid using it from within subprocess targets.

Usage Pattern:
This module is designed to be implicitly loaded by CLI entrypoints.

Avoid using whiteprints.cli.ENV inside subprocess targets.
The import is fine — but ENV is lazy and re-parses config from disk,
which can cause divergence or security leakage. Always pass down ENV-derived
values explicitly.
"""

import gettext
from collections.abc import Callable
from functools import cache
from threading import Lock
from types import FrameType
from typing import TYPE_CHECKING, Final, Literal, NoReturn, cast

from whiteprints.concurrency import is_main_process, is_main_thread
from whiteprints.custom_exceptions import format_exception_chain
from whiteprints.exit_codes import ExitCode
from whiteprints.layered_env import Environment
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import (
    import_extra,
    import_lazy,
    import_lazy_project,
)
from whiteprints.libconfig.config_exceptions import ConfigLoaderError
from whiteprints.package_constants import DISTRIBUTION_NAME
from whiteprints.signals_handler import DelaySignals


__all__: Final = [
    "ConfigLoaderError",
    "exit_gracefully_on_signal",
    "format_exception_chain",
    "is_main_process",
    "robust_print",
    "robust_print_json",
]
"""Public module attributes."""


robust_print = print if (rich := import_extra("rich")) is None else rich.print
"""A rich print function with fallback on Python print if rich is not found."""


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
        import_lazy("json").dump(
            data,
            import_lazy("sys").stdout,
            indent=indent,
            skipkeys=skip_keys,
            ensure_ascii=ensure_ascii,
            check_circular=check_circular,
            allow_nan=allow_nan,
            sort_keys=sort_keys,
            default=default,
        )
        import_lazy("sys").stdout.write("\n")
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


def _resolve_path(path: str) -> str:
    os = import_lazy("os")
    return os.path.normcase(os.path.abspath(os.path.expanduser(path)))


def _resolve_stream(stream: str) -> str:
    stream = stream.lower()
    if stream in {"stdout", "stderr"}:
        return f"ext://sys.{stream}"

    return stream


def _get_env() -> Environment:
    """Retrive the environement variables.

    Returns:
        The current environment variables from os.environ and files.
    """
    distribution_name = DISTRIBUTION_NAME.upper()
    path_redactor = import_lazy_project("redactor").PathRedactor()
    return import_lazy_project("layered_env").Environment(
        environment_variables={
            "VIRTUAL_ENV",
            f"{distribution_name}_LOG_LEVEL",
            f"{distribution_name}_LOG_STRUCT",
            f"{distribution_name}_LOG_STREAM",
            f"{distribution_name}_LOG_MODE_TRACEBACK",
            f"{distribution_name}_LOG_MODE_STACKTRACE",
            f"{distribution_name}_LOG_CONFIG",
        },
        environment_variables_regex=set(),
        sensitive_variables={
            "VIRTUAL_ENV": path_redactor,
            f"{distribution_name}_LOG_CONFIG": path_redactor,
        },
        secret_variables=set(),
        transform_variables={
            f"{distribution_name}_LOG_LEVEL": str.upper,
            f"{distribution_name}_LOG_STRUCT": str.lower,
            f"{distribution_name}_LOG_STREAM": _resolve_stream,
            f"{distribution_name}_LOG_MODE_TRACEBACK": str.lower,
            f"{distribution_name}_LOG_MODE_STACKTRACE": str.lower,
            f"{distribution_name}_LOG_CONFIG": _resolve_path,
        },
    )


def _exit_gracefully_action(signalnum: int, _frame: FrameType) -> NoReturn:
    """Exit gracefully when a signal is caught.

    The programs exit with the error code being the signal number.

    Args:
        signalnum: the signal number.
        _frame: the stack frame.
    """
    print("SIGNAL INTERCEPTED", import_lazy("os").getpid())
    cast(
        "ExitCode",
        import_lazy_project("exit_codes").from_signal(signalnum),
    ).exit()


_SIGNAL_LOCK: Final = Lock()


def exit_gracefully_on_signal() -> None:
    """Register SIGINT and SIGTERM handlers exactly once in main process."""
    with DelaySignals(), _SIGNAL_LOCK:
        if is_main_thread():
            signal = import_lazy("signal")
            signal.signal(signal.SIGINT, _exit_gracefully_action)
            signal.signal(signal.SIGTERM, _exit_gracefully_action)


exit_gracefully_on_signal()

gettext.bindtextdomain(
    "argparse",
    _.locale_directory,
)
gettext.textdomain("argparse")


@cache
def __getattr__(name: Literal["ENV"]) -> Environment:
    """Lazily resolve the top-level ENV singleton.

    The Environment instance is lazily created on first access in each
    process or interpreter. This means that accessing `ENV` in a subprocess
    (via import or direct use) will recreate and re-parse the environment
    layers independently.

    To avoid redundant file I/O and maintain consistency, users should
    resolve required values from `ENV` in the parent process and pass them
    explicitly to child processes or subprocesses at initialization.

    Args:
        name: Must be the string "ENV".

    Returns:
        The singleton Environment instance.

    Raises:
        AttributeError: If `name` is not "ENV".
    """
    if name == "ENV":
        return _get_env()

    raise AttributeError(name)


if TYPE_CHECKING:
    ENV: Environment
