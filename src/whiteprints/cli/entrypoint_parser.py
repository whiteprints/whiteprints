# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The entrypoint arguments parser."""

import importlib
import sys
from argparse import (
    ArgumentParser,
    HelpFormatter,
    Namespace,
)
from types import ModuleType
from typing import (
    Final,
    Literal,
    NoReturn,
    cast,
)

from whiteprints import _, has_extra, import_extra
from whiteprints.cli import robust_print, robust_print_json
from whiteprints.cli.action import (
    CompleterAction,
    Completion,
    Copyright,
    License,
    Version,
)


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
        self.exit(
            importlib.import_module("os").EX_USAGE,
            _("{}: error: {}\n").format(self.prog, message),
        )


def _nargs_completion_script() -> Literal["?", 1]:
    """Find how many arguments '--autocompletion-script' should take.

    Returns:
        '?' if shellingham is installed, 1 otherwise.
    """
    return "?" if has_extra("shellingham") else 1


def _nargs_license_text(licenses: list[str]) -> Literal[0, 1]:
    """Find how many arguments --license-text should take.

    Returns:
        0 if the program have a single license, 1 otherwise.
    """
    return 0 if len(licenses) <= 1 else 1


def _initialize_parser(
    prog: str,
    app_name_env_prefix: str,
    theme: str | None,
    epilog: str | None,
    rich_argparse_plus: ModuleType | None,
) -> ArgumentParserExUsage:
    """Initialize the argument parser.

    Args:
        prog: the program name.
        app_name_env_prefix: a prefix for the environment variables used to
            configure the program.
        theme: an optional theme (supported by rich-argparse-plus).
        epilog: the program epilog text.
        rich_argparse_plus: an optional rich_argparse_plus module.

    Returns:
        The argument parse.
    """
    if rich_argparse_plus is not None:
        formatter_class = rich_argparse_plus.RichHelpFormatterPlus
        try:
            formatter_class.choose_theme(theme)
        except ValueError as value_error:
            robust_print(value_error)
            sys.exit(importlib.import_module("os").EX_USAGE)

        formatter_class = importlib.import_module("functools").partial(
            formatter_class,
            width=(
                str(width)
                if (
                    width := importlib.import_module("os").environ.get(
                        f"{app_name_env_prefix}_HELP_WIDTH"
                    )
                )
                else None
            ),
        )
    else:
        formatter_class = HelpFormatter

    return ArgumentParserExUsage(
        prog=prog,
        formatter_class=formatter_class,
        description=_(
            "A Copier-based cookiecutter for creating Python projects managed"
            "by UV."
        ),
        add_help=False,
        epilog=epilog,
    )


def _add_program_info(parser: ArgumentParser) -> None:
    """Add flags to show program information.

    Args:
        parser: the program argument parser.
    """
    (
        program_info := parser.add_argument_group(_("Program Info"))
    ).add_argument(
        "-h",
        "--help",
        action="help",
        help=_("Show this help message and exit."),
    )
    program_info.add_argument(
        "-v",
        "--version",
        nargs=0,
        action=Version,
        help=_("Show program's version number and exit."),
    )
    program_info.add_argument(
        "-c",
        "--copyright",
        nargs=0,
        action=Copyright,
        help=_("Show the copyright information and exit."),
    )


def _add_licensing_info(parser: ArgumentParser) -> None:
    """Add flags to show program licenses.

    Args:
        parser: the program argument parser.
    """
    (licensing := parser.add_argument_group(_("Licensing Info"))).add_argument(
        "-l",
        "--license",
        action="count",
        help=_(
            "Show the license expression and exit."
            " Repeat the flag to show REUSE information."
        ),
    )
    licensing.add_argument(
        "-t",
        "--license-text",
        nargs=_nargs_license_text(
            licenses := [
                (os := importlib.import_module("os")).path.splitext(
                    os.path.basename(license_path)
                )[0]
                for license_path in importlib.import_module(
                    "whiteprints.metadata",
                ).extract_fields("License-File")
            ]
        ),
        action=License,
        choices=licenses,
        help=_("Show the license text and exit."),
    )


def _add_debug_info(parser: ArgumentParser) -> None:
    """Add flags to show debug information.

    Args:
        parser: the program argument parser.
    """
    parser.add_argument_group(_("Debug Info")).add_argument(
        "-p",
        "--platform",
        action="count",
        help=_(
            "Show platform and environment information and exit."
            " Repeat the flag to add distribution information."
        ),
    )


def _add_autocompletion(parser: ArgumentParser) -> None:
    """Add flags to generate autocompletion.

    Args:
        parser: the program argument parser.
    """
    if has_extra("argcomplete"):
        parser.add_argument_group(_("Completion")).add_argument(
            "-a",
            "--autocompletion-script",
            nargs=_nargs_completion_script(),
            action=Completion,
            choices=Completion.SUPPORTED_SHELLS,
            help=_("Show the completion script code and exit."),
        )


def _add_configuration_parsers(
    parser: ArgumentParser,
    app_name_env_prefix: str,
    argcomplete: ModuleType | None,
) -> None:
    """Add flags to change the program behaviour (configuration).

    Args:
        parser: the program argument parser.
        app_name_env_prefix: the environment variable prefix name for the
            program.
        argcomplete: an optional argcomplete module.
    """
    logs_arg = cast(
        "CompleterAction",
        parser.add_argument_group(_("Configuration")).add_argument(
            "-L",
            "--log-config",
            action="store",
            help=(
                _(
                    "Loads the logging configuration file (JSON format)"
                    " at this location. If an empty string{} is passed, the"
                    " default Python configuration is used, with"
                    ' LOGLEVEL="CRITICAL". If the file does not exists,'
                    " a default configuration file is created at the specified"
                    " location and loaded. You may change the default path"
                    " with the environment variable `{}`."
                ).format(
                    ""
                    if (
                        logs_conf_default := (
                            importlib.import_module("os").environ.get(
                                logs_conf_env := (
                                    f"{app_name_env_prefix}_DEFAULT_LOGS_CONF"
                                ),
                                (
                                    importlib.import_module(
                                        "whiteprints.cli.logs"
                                    ).user_log_config()
                                    or ""
                                ),
                            )
                        )
                    )
                    else _(" or none"),
                    logs_conf_env,
                )
            ),
            metavar="PATH",
            default=logs_conf_default,
        ),
    )
    if argcomplete is not None:
        logs_arg.completer = argcomplete.FilesCompleter(allowednames=".json")


def create_entrypoint_parser(prog: str) -> ArgumentParserExUsage:
    """Parse command line arguments.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Example:
        >>> isinstance(create_entrypoint_parser("prog"), ArgumentParser)
        True

    Args:
        prog: the program name.

    Returns:
        the program namespace.
    """
    parser = _initialize_parser(
        prog,
        app_name_env_prefix := prog.upper(),
        importlib.import_module("os").environ.get(
            theme_env := f"{app_name_env_prefix}_THEME", "default"
        ),
        (
            _(
                "You may change the CLI color theme with the environment"
                " variable `{}`."
            ).format(theme_env)
            if (rich_argparse_plus := import_extra("rich_argparse_plus"))
            else None
        ),
        rich_argparse_plus,
    )

    _add_program_info(parser)
    _add_licensing_info(parser)
    _add_debug_info(parser)
    _add_autocompletion(parser)
    _add_configuration_parsers(
        parser,
        app_name_env_prefix,
        import_extra("argcomplete"),
    )

    return parser


def _resolve_platform_flag(namespace: Namespace) -> None:
    """Resolve the `--platform` flag.

    Args:
        namespace: the program namespace.
    """
    if isinstance(namespace.platform, int) and namespace.platform > 0:
        robust_print_json(
            data=importlib.import_module(
                "whiteprints.debug_info",
            ).gather_debug_info(site_packages=(namespace.platform > 1)),
            indent=None,
        )
        sys.exit(importlib.import_module("os").EX_OK)


def _resolve_license_flag(namespace: Namespace) -> None:
    """Resolve the `--license` flag.

    Args:
        namespace: the program namespace.
    """
    if isinstance(namespace.license, int):
        license_expression = importlib.import_module(
            "whiteprints.metadata",
        ).extract_field("License-Expression")
        if namespace.license == 1:
            robust_print(license_expression)

        if namespace.license > 1:
            robust_print_json(
                data={
                    "SPDX-License-Identifier": license_expression,
                    "DISCLAIMER": _(
                        "This project is REUSE compliant."
                        " Check the SPDX header of each"
                        " individual source code file"
                        " for detailed licensing information."
                    ).format(),
                    "source_code_location": str(
                        (os := importlib.import_module("os")).path.dirname(
                            os.path.dirname(__file__)
                        )
                    ),
                    "REUSE": "https://reuse.software/",
                },
                indent=None,
            )

        sys.exit(importlib.import_module("os").EX_OK)


def _resolve_help_action(
    namespace: Namespace, argument_parser: ArgumentParser
) -> None:
    """Resolve the `--help` flag.

    Args:
        namespace: the program namespace.
        argument_parser: the program argument parser.
    """
    if namespace.cmd is None:
        argument_parser.print_help()
        sys.exit(importlib.import_module("os").EX_OK)


def resolve_flags(
    argument_parser: ArgumentParser,
    namespace: Namespace,
) -> None:
    """Resolve remaining flags.

    Args:
        argument_parser: the program argument parser.
        namespace: the program namespace.
    """
    _resolve_platform_flag(namespace)
    _resolve_license_flag(namespace)
    _resolve_help_action(namespace, argument_parser)
