# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The entrypoint arguments parser."""

import importlib
import os
import sys
from argparse import Action, ArgumentParser, HelpFormatter, Namespace
from collections.abc import Iterable
from functools import partial
from pathlib import Path
from typing import ClassVar, Final, NoReturn, Optional

from whiteprints import _, robust_print, robust_print_json


if sys.version_info >= (3, 10):
    from importlib.metadata import PackagePath
else:
    from importlib_metadata import PackagePath

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


__all__: Final = ["create_entrypoint_parser"]


class ArgumentParserExUsage(ArgumentParser):
    """An ArgumentParser subclass that exit with code os.EX_USAGE on error."""

    @override
    def error(self, message: str) -> NoReturn:
        """Error message.

        Args:
            message: The error message.
        """
        self.print_usage(sys.stderr)
        self.exit(os.EX_USAGE, _("{}: error: {}\n").format(self.prog, message))


def try_detect_shell(prog: str) -> str:
    """Try to detect the shell name.

    If the module `shellingham` is not installed exit with return code
    `os.EX_SOFTWARE`.

    Args:
        prog: the program name.

    Returns:
        The name of the shell.
    """
    try:
        return importlib.import_module("shellingham").detect_shell()[0]
    except ModuleNotFoundError:
        robust_print(
            _(
                "error: no shell detection plugin installed. reinstall"
                " `{prog}` with the `qol` extra"
                " (e.g. `pip install {prog}"
                r"\[qol]`) to use autocompletion."
            ).format(prog=prog),
            fallback_message=_(
                "error: no shell detection plugin installed. Reinstall"
                " `{prog}` with the `qol` extra"
                " (e.g. `pip install {prog}"
                r"[qol]`) to use autocompletion."
            ).format(prog=prog),
            file=sys.stderr,
        )
        sys.exit(os.EX_SOFTWARE)


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
        maybe_shell = args[0]
        shell = (
            try_detect_shell(parser.prog)
            if maybe_shell is None
            else str(maybe_shell)
        )
        try:
            # Bandit has a false positive. Here shell is a string not a
            # boolean. More importantly it is not related to a subprocess
            # execution simply the shell choice for completion.
            robust_print(
                importlib.import_module("argcomplete.shell_integration")
                .shellcode([parser.prog], shell=shell)  # nosec
                .strip()
            )
        except ModuleNotFoundError:
            robust_print(
                _(
                    "error: no autocompletion plugin installed. reinstall"
                    " `{prog}` with the `qol` extra"
                    " (e.g. `pip install {prog}"
                    r"\[qol]`) to use autocompletion."
                ).format(prog=parser.prog),
                fallback_message=_(
                    "error: no autocompletion plugin installed. Reinstall"
                    " `{prog}` with the `qol` extra"
                    " (e.g. `pip install {prog}"
                    r"[qol]`) to use autocompletion."
                ).format(parser.prog),
                file=sys.stderr,
            )
            sys.exit(os.EX_SOFTWARE)

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
        robust_print(
            _(
                'Copyright © 2024 The "Whiteprints" contributors'
                " <whiteprints@pm.me>."
            )
        )

        sys.exit(os.EX_OK)


def print_lincense_files(
    requested_license: str,
    license_files: Iterable[PackagePath],
) -> NoReturn:
    """Print the requested license file content.

    Args:
        requested_license: The requested license name.
        license_files: a collection of paths to license.
    """
    for license_path in license_files:
        if requested_license in license_path.stem:
            robust_print(license_path.read_text())
            sys.exit(os.EX_OK)

    error_message = _("error: license {} not found").format(requested_license)
    robust_print(
        f"[red]{error_message}[/]",
        fallback_message=error_message,
    )
    sys.exit(os.EX_USAGE)


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
        requested_license = args[0]
        if requested_license is None:
            robust_print_json(
                data={
                    "SPDX-License-Identifier": (
                        package_metadata.find_license_expression()
                    ),
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

        print_lincense_files(
            str(requested_license),
            package_metadata.find_license_files(),
        )


def create_entrypoint_parser(prog: str) -> ArgumentParserExUsage:
    """Parse command line arguments.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Example:
        >>> isinstance(create_entrypoint_parser("prog"), ArgumentParser)
        True

    Args:
        prog: the program name

    Returns:
        the arguments namespace.
    """
    try:
        formatter_class = partial(
            importlib.import_module("rich_argparse").RichHelpFormatter,
            indent_increment=4,
        )
    except ModuleNotFoundError:
        formatter_class = HelpFormatter

    parser = ArgumentParserExUsage(
        prog=prog,
        formatter_class=formatter_class,
        description=importlib.import_module(
            "importlib.metadata"
        ).find_metadata()["Summary"],
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
        ).find_version(),
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
            ).find_license_files()
        ],
        help=_("Show the license information and exit."),
    )

    program_info.add_argument(
        "-d",
        "--debug",
        action="count",
        help=_("Show debugging information and exit. "),
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
    app_name_env_prefix = prog.upper()
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


def resolve_flags(
    argument_parser: ArgumentParser,
    namespace: Namespace,
) -> None:
    if namespace.debug is not None and namespace.debug > 0:
        robust_print_json(
            data=importlib.import_module(
                "whiteprints.debug_info",
                __package__,
            ).gather_debug_info(dependencies=(namespace.debug > 1)),
            indent=None,
        )
        sys.exit(os.EX_OK)

    if namespace.cmd is None:
        argument_parser.print_help()
        sys.exit(os.EX_OK)
