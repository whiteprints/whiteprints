# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'Hello world' command.."""

import importlib

import rich_click as click

from whiteprints.loc import _


@click.command(name=_("hello-world"), help=_("Say 'Hello, World!'."))
def hello_world() -> None:
    """This is a demonstration command.

    Print "Hello, World!" on the standard output.

    Remove or edit this function to build your own CLI!
    """
    console = importlib.import_module("whiteprints.console", __package__)
    console.STDOUT.print("Hello, World!")
