# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# PYTHON_ARGCOMPLETE_OK

"""Command Line Interface app entrypoint."""

import importlib
import importlib.metadata
import sys
from argparse import Namespace
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any, Final, Optional, no_type_check

from whiteprints import _, maybe_import_module


__all__: Final = ["entrypoint", "prog_name"]
"""Public module attributes."""


if sys.version_info >= (3, 11):

    def no_type_check_context_manager(
        function: Callable[..., Any],
    ) -> Callable[..., Any]:
        return function

else:
    no_type_check_context_manager = no_type_check


@cache
def prog_name() -> str:
    """Determine the program name from the entrypoint metadata.

    Returns:
        The program name.
    """
    entrypoint_value = f"{__name__}:entrypoint"
    entrypoints = importlib.metadata.entry_points()

    if sys.version_info >= (3, 10):
        names = entrypoints.select(
            group="console_scripts",
            value=entrypoint_value,
        ).names
    else:
        names = {
            entrypoint.name
            for entrypoint in entrypoints["console_scripts"]
            if entrypoint.value == entrypoint_value
        }

    if names:
        return names.pop()

    return Path(sys.argv[0]).stem


@no_type_check_context_manager
@contextmanager
def gc_disabled() -> Iterator[None]:
    """Temporarily disable the garbage collector for performances."""
    (gc := importlib.import_module("gc")).disable()
    yield
    gc.enable()
    gc.collect()


def _create_namespace(
    args: Optional[list[str]],
    argcomplete: Optional[ModuleType],
) -> Namespace:
    """Create a namespace from the arguments.

    Args:
        args: the command line arguments.
        argcomplete: an optional argcomplete module.

    Returns:
        The namespace corresponding to the arguments passed.
    """
    (gettext := importlib.import_module("gettext")).bindtextdomain(
        "argparse",
        _.locale_directory,
    )
    gettext.textdomain("argparse")

    subparsers = (
        entrypoint_parser := importlib.import_module(
            "whiteprints.cli.entrypoint_parser",
        ).create_entrypoint_parser(prog_name())
    ).add_subparsers(
        title=_("Subcommands"),
        dest="cmd",
    )
    importlib.import_module(
        "whiteprints.cli.command.init_parser",
    ).setup_init_parser(
        subparsers.add_parser(
            "init",
            formatter_class=entrypoint_parser.formatter_class,
            description=_("Initialize a Python project."),
            help=_("Initialize a Python project."),
            exit_on_error=False,
            add_help=False,
            epilog=_(
                "Note: see https://copier.readthedocs.io/en/stable/configuring/"
                " for help on how to use Copier and COPIER_ARGS"
                " (optional)."
            ),
        )
    )

    if argcomplete is not None:
        argcomplete.autocomplete(entrypoint_parser)

    importlib.import_module(
        "whiteprints.cli.entrypoint_parser",
    ).resolve_flags(
        entrypoint_parser, namespace := entrypoint_parser.parse_args(args)
    )

    return namespace


def _setup_logging(namespace: Namespace) -> None:
    """Setup the logging.

    Use the configuration provided in the namespace.

    Args:
        namespace: the arguments namespace.
    """
    importlib.import_module(
        "whiteprints.cli.logs",
    ).setup_logging(
        Path(namespace.log_config) if namespace.log_config else None,
    )
    logger = importlib.import_module("logging").getLogger(__name__)
    logger.debug(
        "program start",
        extra={
            "debug_info": (
                lambda: (
                    importlib.import_module(
                        "whiteprints.debug_info",
                    ).gather_debug_info()
                )
            ),
            "namespace": namespace.__dict__,
        },
    )


def _call_command(namespace: Namespace) -> None:
    """Call a command.

    This is done by lazily loading the whiteprint module named after the
    command and the calling a function with the same name as the module name.

    Args:
        namespace: the arguments namespace.
    """
    command = importlib.import_module(
        f"whiteprints.cli.command.{namespace.cmd}",
    )
    getattr(command, namespace.cmd)(namespace)


def entrypoint(args: Optional[list[str]] = None) -> None:
    """The Whiteprint CLI.

    Example:
        >>> import os
        >>>
        >>> try:
        >>>     entrypoint([])
        >>> except SystemExit as ext:
        >>>     assert ext.code == os.EX_OK
        ...

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.
    """
    with gc_disabled():
        # Delay the gc for a short time to have the CLI as responsive as
        # possible.
        # There should be no objects with cyclic references created. Even
        # if some are created for this short amount they will be collected
        # as soon as the namespace is created.
        namespace = _create_namespace(
            args,
            maybe_import_module("argcomplete"),
        )

    _setup_logging(namespace)
    _call_command(namespace)

    importlib.import_module("logging").getLogger(__name__).debug(
        "program exit without error"
    )
