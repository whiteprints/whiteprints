# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The entrypoint arguments parser."""

import importlib
import os
import sys
from argparse import Action, ArgumentParser
from functools import cache
from pathlib import Path
from typing import Final, NoReturn

from whiteprints.console import stdout
from whiteprints.loc import _


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["create_entrypoint_parser"]


class Copyright(Action):
    """Print the code licenses information."""

    @override
    def __call__(self, *args: object) -> NoReturn:
        """Print the code copyright information.

        Args:
            args: all arguments passed are ignored.
        """
        stdout().print(
            _(
                'Copyright © 2024 The "Whiteprints" contributors'
                " <whiteprints@pm.me>."
            ),
        )
        sys.exit(os.EX_OK)


class License(Action):
    """Print the code licenses information."""

    @override
    def __call__(self, *args: object) -> NoReturn:
        """The action callback.

        Args:
            args: all arguments passed are ignored.
        """
        package_metadata = importlib.import_module(
            "whiteprints.package_metadata"
        )
        stdout().print(
            _("Code released under license '{}'.").format(
                package_metadata.__license__
            )
        )
        stdout().print(
            _(
                "\nThis project is REUSE compliant ('https://reuse.software/')."
                " Please check the SPDX header of each source code file for "
                "detailed licensing information.\nSources are located at "
                "'{}'.\n"
            ).format(Path(__file__).parent.parent)
        )

        panel = importlib.import_module("rich.panel")
        box = importlib.import_module("rich.box")
        for license_path in package_metadata.__license_file__:
            license_panel = panel.Panel(
                license_path.read_text(),
                box=box.HORIZONTALS,
                title=license_path.stem,
                subtitle=str(license_path.locate()),
            )
            stdout().print(license_panel)

        sys.exit(os.EX_OK)


class DebugInfo(Action):
    """Print system information for debug."""

    @override
    def __call__(self, *args: object) -> NoReturn:
        """The action callback.

        Args:
            args: all arguments passed are ignored.
        """
        stdout().print_json(
            data=importlib.import_module(
                "whiteprints.debug_info",
                __package__,
            ).gather_debug_info(),
            indent=4,
        )
        sys.exit(os.EX_OK)


@cache
def create_entrypoint_parser() -> ArgumentParser:
    """Parse command line arguments.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.

    Returns:
        the arguments namespace.
    """
    app_name = importlib.import_module(
        "whiteprints.cli.app_metadata",
        __package__,
    ).app_name()

    parser = ArgumentParser(
        prog=app_name,
        formatter_class=importlib.import_module(
            "rich_argparse"
        ).RichHelpFormatter,
        description=_(
            "A Copier-based cookiecutter for creating Python projects "
            "managed by uv."
        ),
        exit_on_error=False,
    )

    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=importlib.import_module(
            "whiteprints.package_metadata",
            __package__,
        ).__version__,
    )

    parser.add_argument(
        "-c",
        "--copyright",
        nargs=0,
        action=Copyright,
        help=_("show the copyright information and exit"),
    )

    parser.add_argument(
        "-l",
        "--license",
        nargs=0,
        action=License,
        help=_("show the license information and exit"),
    )

    parser.add_argument(
        "-d",
        "--debug-info",
        nargs=0,
        action=DebugInfo,
        help=_("show debugging information and exit"),
    )

    app_name_env_prefix = app_name.replace("-", "_").upper()
    log_conf_metavar = f"{app_name_env_prefix}_LOG_CONF"
    parser.add_argument(
        "-L",
        "--log-conf",
        action="store",
        type=Path,
        help=(
            _("logging configuration file [[grey62]%s[/]]") % log_conf_metavar
        ),
        metavar="PATH",
        default=os.environ.get(log_conf_metavar),
    )
    return parser
