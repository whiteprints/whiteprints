# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command Line Interface app entrypoint."""

from __future__ import annotations

import importlib
import os
import sys
from functools import cached_property
from pathlib import Path
from typing import Final, TextIO, TypedDict, cast, get_args

import rich_click as click
from rich_click import Context, File, Option
from rich_click.rich_command import RichCommand as Command
from rich_click.rich_command import RichGroup as Group

from whiteprints import __version__
from whiteprints.cli import APP_NAME, __app_name__
from whiteprints.cli.logs import LogLevel, configure_logging
from whiteprints.loc import _


if sys.version_info < (3, 11):
    from typing_extensions import Unpack
else:
    from typing import Unpack


if sys.version_info < (3, 12):
    from typing_extensions import override
else:
    from typing import override


__all__: Final = ["whiteprints"]
"""Public module attributes."""


COMMAND_DIRECTORY_NAME: Final = "command"
COMMAND_ROOT: Final = Path(__file__).parent / COMMAND_DIRECTORY_NAME


class LazyCommandLoader(Group):
    """Lazy commands loader.

    Loads lazily all the commands in the submodule .command.
    """

    @staticmethod
    def _is_command(obj: object) -> bool:
        """Check if an object is a command.

        Args:
            obj: a Python object.

        Returns:
            True if the object is a Command, False otherwise.
        """
        return isinstance(obj, Command)

    @cached_property
    def command_lookup(self) -> dict[str, dict[str, str]]:
        """A command lookup table."""
        pkgutil = importlib.import_module("pkgutil")
        commands_modules = [
            ".".join((__package__ or "", COMMAND_DIRECTORY_NAME, name))
            for _module_finder, name, _ispkg in pkgutil.walk_packages(
                path=map(str, [COMMAND_ROOT])
            )
        ]
        inspect = importlib.import_module("inspect")
        command_lookup: dict[str, dict[str, str]] = {}
        for module in commands_modules:
            for command in inspect.getmembers(
                importlib.import_module(module, __package__),
                LazyCommandLoader._is_command,
            ):
                command_lookup[command[1].name] = {
                    "module": module,
                    "function_name": command[0],
                }

        return command_lookup

    @cached_property
    def _list_commands(self) -> list[str]:
        """A list all the commands."""
        return sorted(self.command_lookup.keys())

    @override
    def list_commands(self, ctx: Context) -> list[str]:
        """List all the commands.

        Args:
            ctx: unused.

        Returns:
            A list of commands names.
        """
        return self._list_commands

    @override
    def get_command(self, ctx: Context, cmd_name: str) -> Command | None:
        """Invoke a command.

        The command must have the name of the module.

        Args:
            ctx: the click context (unused).
            cmd_name: the name of the command to invoke.

        Returns:
            A command.
        """
        if (command := self.command_lookup.get(cmd_name)) is None:
            return None

        return cast(
            Command,
            getattr(
                importlib.import_module(
                    command["module"],
                    __package__,
                ),
                command["function_name"],
                cmd_name,
            ),
        )


@override
def print_license(ctx: Context, _param: Option, value: bool) -> None:
    """Print the code licenses information.

    Args:
        ctx: the click Context.
        _param: the click Option.
        value: the value of the option.
    """
    if not value:
        return

    console = importlib.import_module("whiteprints.console")
    package_metadata = importlib.import_module("whiteprints.package_metadata")
    console.STDOUT.print(
        _("Code released under license '{}'.").format(
            package_metadata.__license__
        )
    )
    console.STDOUT.print(
        _(
            "\nThis project is REUSE compliant ('https://reuse.software/')."
            " Please check the SPDX header of each source code file for "
            "detailed licensing information.\nSources located at '{}'.\n"
        ).format(Path(__file__).parent.parent)
    )

    panel = importlib.import_module("rich.panel")
    for license_path in package_metadata.__license_file__:
        license_panel = panel.Panel(
            license_path.read_text(),
            title=license_path.stem,
        )
        console.STDOUT.print(license_panel)
        console.STDOUT.print(str(license_path.locate()) + "\n")

    ctx.exit()


class CLIArgsType(TypedDict):
    """The CLI arguments types."""

    log_level: LogLevel
    log_file: TextIO


@click.command(
    cls=LazyCommandLoader,
    name=__app_name__,
    help=_(
        "Thank you for using {}, a tool to generate minimal Python projects."
    ).format(__app_name__),
    no_args_is_help=True,
)
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(
        get_args(LogLevel),
        case_sensitive=False,
    ),
    help=_("Logging verbosity."),
    default=os.environ.get(f"{APP_NAME}_LOG_LEVEL", "ERROR"),
    show_default=True,
)
@click.option(
    "-f",
    "--log-file",
    type=File(
        mode="w",
        encoding="utf-8",
        lazy=True,
    ),
    help=_("A file in which to write the log."),
    default=os.environ.get(f"{APP_NAME}_LOG_FILE", "-"),
    show_default=True,
)
@click.option(
    "--license",
    is_flag=True,
    callback=print_license,
    expose_value=False,
    is_eager=True,
    help=_("Print the license information."),
)
@click.version_option(version=__version__, prog_name=__app_name__)
def whiteprints(**kwargs: Unpack[CLIArgsType]) -> None:
    """The Whiteprint CLI."""
    configure_logging(
        level=kwargs["log_level"],
        file=kwargs["log_file"],
    )
