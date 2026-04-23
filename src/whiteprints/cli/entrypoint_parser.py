# SPDX-FileCopyrightText: © 2025 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The entrypoint arguments parser."""

from argparse import (
    ArgumentParser,
    Namespace,
)
from types import ModuleType
from typing import (
    Final,
    Literal,
    NoReturn,
    cast,
    override,
)

from whiteprints.cli.entrypoint_parser_action import CompleterAction
from whiteprints.exit_codes import ExitCode
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import (
    has_extra,
    import_extra,
    import_lazy,
    import_lazy_project,
)
from whiteprints.package_constants import DISTRIBUTION_NAME


__all__: Final = ["create_entrypoint_parser"]
"""Public module attributes."""


class ArgumentParserExUsage(ArgumentParser):
    """An ArgumentParser subclass that exit with code os.EX_USAGE on error."""

    @override
    def error(self, message: str) -> NoReturn:
        """Error message.

        Args:
            message: The error message.
        """
        logger = import_lazy_project("cli.logs").LOGGING.get_logger()
        logger.critical(
            "\n".join((
                message,
                _("try '{} --help' for more information"),
            ))
        )
        cast(
            "ExitCode",
            import_lazy_project("exit_codes").COMMAND_LINE_USAGE_ERROR,
        ).log(logger).exit()


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
    epilog: str | None,
    rich_argparse: ModuleType | None,
) -> ArgumentParserExUsage:
    """Initialize the argument parser.

    Args:
        prog: the program name.
        app_name_env_prefix: a prefix for the environment variables used to
            configure the program.
        epilog: the program epilog text.
        rich_argparse: an optional rich_argparse module.

    Returns:
        The argument parse.
    """
    if rich_argparse is not None:
        formatter_class = rich_argparse.RichHelpFormatter
    else:
        formatter_class = import_lazy("argparse").HelpFormatter

    return ArgumentParserExUsage(
        prog=prog,
        formatter_class=formatter_class,
        description=_(
            "A Copier-based cookiecutter for creating Python projects managed"
            " by UV."
        ),
        add_help=False,
        allow_abbrev=False,
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
        action=import_lazy_project("cli.entrypoint_parser_action").Version,
        help=_("Show program's version number and exit."),
    )
    program_info.add_argument(
        "-c",
        "--copyright",
        nargs=0,
        action=import_lazy_project("cli.entrypoint_parser_action").Copyright,
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
        nargs=0,
        action=import_lazy_project("cli.entrypoint_parser_action").License,
        help=_("Show the license expression and exit."),
    )
    licensing.add_argument(
        "-t",
        "--license-text",
        nargs=_nargs_license_text(
            licenses := [
                (os := import_lazy("os")).path.splitext(
                    os.path.basename(license_path)
                )[0]
                for license_path in import_lazy_project(
                    "fast_distinfo_reader"
                ).extract_fields("License-File")
            ]
        ),
        action=import_lazy_project("cli.entrypoint_parser_action").LicenseText,
        choices=licenses,
        help=_("Show the license text and exit."),
    )
    licensing.add_argument(
        "-r",
        "--reuse",
        nargs=0,
        action=import_lazy_project("cli.entrypoint_parser_action").Reuse,
        help=_("Show REUSE metadata and exit."),
    )


def _add_autocompletion(parser: ArgumentParser) -> None:
    """Add flags to generate autocompletion.

    Args:
        parser: the program argument parser.
    """
    if has_extra("argcomplete"):
        action = import_lazy_project("cli.entrypoint_parser_action")
        parser.add_argument_group(_("Completion")).add_argument(
            "-a",
            "--autocompletion-script",
            nargs=_nargs_completion_script(),
            action=action.Completion,
            choices=action.Completion.SUPPORTED_SHELLS,
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
                    "Load TOML logging config file; creates default if file is"
                    " missing. (env: {})"
                ).format(
                    f"{app_name_env_prefix}_LOG_CONF",
                )
            ),
            metavar="PATH",
        ),
    )
    if argcomplete is not None:
        logs_arg.completer = argcomplete.FilesCompleter(allowednames=".toml")


def create_entrypoint_parser() -> ArgumentParserExUsage:
    """Parse command line arguments.

    The ouput of this function is cached. No new instances are created on
    subsequent calls.

    Example:
        >>> isinstance(create_entrypoint_parser(), ArgumentParser)
        True

    Returns:
        the program namespace.
    """
    app_name_env_prefix = DISTRIBUTION_NAME.upper()
    parser = _initialize_parser(
        DISTRIBUTION_NAME,
        "",
        import_extra("rich_argparse"),
    )

    _add_program_info(parser)
    _add_licensing_info(parser)
    _add_autocompletion(parser)
    _add_configuration_parsers(
        parser,
        app_name_env_prefix,
        import_extra("argcomplete"),
    )

    return parser


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
        cast("ExitCode", import_lazy_project("exit_codes").SUCCESS).exit()


def resolve_flags(
    argument_parser: ArgumentParser,
    namespace: Namespace,
) -> None:
    """Resolve remaining flags.

    Args:
        argument_parser: the program argument parser.
        namespace: the program namespace.
    """
    _resolve_help_action(namespace, argument_parser)
