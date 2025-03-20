# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The entrypoint arguments parser."""

import importlib
import os
import sys
from argparse import Action, ArgumentParser, HelpFormatter, Namespace
from functools import cache, partial
from pathlib import Path
from typing import ClassVar, Final, NoReturn, Optional

from whiteprints import LOCALE_DIRECTORY, _, stderr, stdout


if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["create_entrypoint_parser"]


class Completion(Action):
    """Print the code licenses information."""

    SUPPORTED_SHELLS: ClassVar = (
        "bash",
        "zsh",
        "tcsh",
        "fish",
        "powershell",
    )

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Optional[object],
    ) -> NoReturn:
        """Generate the autocompletion code.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        shell_arg = args[0]
        try:
            shell_integration = importlib.import_module(
                "argcomplete.shell_integration"
            )
            shell = (
                importlib.import_module("shellingham").detect_shell()[0]
                if shell_arg is None
                else args[0]
            )
        except ModuleNotFoundError:
            stderr().print(
                _(
                    "No autocompletion installed. Reinstall"
                    " `{app_name}` with the `qol` extra"
                    " (e.g. `pip install {app_name}"
                    r"\[qol]`) to use autocompletion."
                ).format(
                    app_name=importlib.import_module(
                        "whiteprints.cli.app_metadata"
                    ).app_name()
                ),
            )
            sys.exit(os.EX_USAGE)

        stdout().print(
            shell_integration.shellcode(
                [
                    importlib.import_module(
                        "whiteprints.cli.app_metadata",
                        __package__,
                    ).app_name()
                ],
                shell=shell,
            ).strip()
        )
        sys.exit(os.EX_OK)


class Copyright(Action):
    """Print the code licenses information."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Optional[object],
    ) -> NoReturn:
        """Print the code copyright information.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
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
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Optional[object],
    ) -> NoReturn:
        """The action callback.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        package_metadata = importlib.import_module(
            "whiteprints.package_metadata",
            __package__,
        )
        if args[0] is None:
            stdout().print_json(
                data={
                    "SPDX-License-Identifier": package_metadata.__license__,
                    "DISCLAIMER": _(
                        "This project is REUSE compliant."
                        " Check the SPDX header of each"
                        " individual source code file"
                        " for detailed licensing information."
                    ).format(),
                    "source_code_location": str(Path(__file__).parent.parent),
                    "REUSE": "https://reuse.software/",
                },
                indent=None,
            )
            sys.exit(os.EX_OK)

        for license_path in package_metadata.__license_file__:
            if args[0] in license_path.stem:
                stdout().print(license_path.read_text())

        sys.exit(os.EX_OK)


class DebugInfo(Action):
    """Print system information for debug."""

    @override
    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        *args: Optional[object],
    ) -> NoReturn:
        """The action callback.

        Args:
            parser: the argument parser
            namespace: the arguments namespace
            args: the arguments passed to the parser
        """
        stdout().print_json(
            data=importlib.import_module(
                "whiteprints.debug_info",
                __package__,
            ).gather_debug_info(),
            indent=None,
        )
        sys.exit(os.EX_OK)


@cache
def create_entrypoint_parser() -> ArgumentParser:
    """Parse command line arguments.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Example:
        >>> create_entrypoint_parser()
        ArgumentParser(...)

    Args:
        args: the arguments forwarded to argparse. For example sys.argv.

    Returns:
        the arguments namespace.
    """
    gettext = importlib.import_module("gettext")
    gettext.bindtextdomain(
        "argparse",
        LOCALE_DIRECTORY,
    )
    gettext.textdomain("argparse")

    app_name = importlib.import_module(
        "whiteprints.cli.app_metadata",
        __package__,
    ).app_name()

    try:
        formatter_class = partial(
            importlib.import_module("rich_argparse").RichHelpFormatter,
            console=stdout(),
            indent_increment=4,
        )
    except ModuleNotFoundError:
        formatter_class = HelpFormatter

    parser = ArgumentParser(
        prog=app_name,
        formatter_class=formatter_class,
        description=_(
            "A Copier-based cookiecutter for creating Python projects "
            "managed by uv."
        ),
        exit_on_error=False,
        add_help=False,
    )

    program_info = parser.add_argument_group("Program Info")
    program_info.add_argument(
        "-h",
        "--help",
        action="help",
        help=_("Show this help message and exit."),
    )

    program_info.add_argument(
        "-v",
        "--version",
        action="version",
        version=importlib.import_module(
            "whiteprints.package_metadata",
            __package__,
        ).__version__,
        help=_("Show program's version number and exit."),
    )

    program_info.add_argument(
        "-c",
        "--copyright",
        nargs=0,
        action=Copyright,
        help=_("Show the copyright information and exit."),
    )

    program_info.add_argument(
        "-l",
        "--license",
        nargs="?",
        action=License,
        choices=[
            license_path.stem
            for license_path in importlib.import_module(
                "whiteprints.package_metadata",
                __package__,
            ).__license_file__
        ],
        help=_("Show the license information and exit."),
    )

    program_info.add_argument(
        "-d",
        "--debug",
        nargs=0,
        action=DebugInfo,
        help=_("Show debugging information and exit."),
    )

    completion = parser.add_argument_group("Completion")
    completion.add_argument(
        "-C",
        "--completion-script",
        nargs="?",
        action=Completion,
        choices=Completion.SUPPORTED_SHELLS,
        help=_("Show the completion script code and exit."),
    )

    logs = parser.add_argument_group("Logging")
    app_name_env_prefix = app_name.replace("-", "_").upper()
    log_conf_metavar = f"{app_name_env_prefix}_LOG_CONF"
    logs_arg = logs.add_argument(
        "-L",
        "--log-config",
        action="store",
        help=_("JSON logging configuration (env: {}).").format(
            log_conf_metavar
        ),
        metavar="PATH",
        default=os.environ.get(log_conf_metavar),
    )
    completer = getattr(logs_arg, "completer", None)
    if completer is not None:
        completer = importlib.import_module("argcomplete").FilesCompleter(
            allowednames=".json"
        )

    return parser
