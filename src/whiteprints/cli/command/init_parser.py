# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'init' subcommand."""

from argparse import ArgumentParser
from typing import Final, cast

from whiteprints.cli.entrypoint_parser_action import CompleterAction
from whiteprints.lazy_gettext import _
from whiteprints.lazy_import import import_extra, import_lazy


__all__: Final = ["setup_init_parser"]
"""Public module attributes."""


def setup_init_parser(parser: ArgumentParser) -> None:
    """Add a subparser to initialize a Python project.

    Args:
        parser: the main parser use to forward the `formatter_class`.

    Example:
        >>> main_parser = ArgumentParser()
        >>> subparsers = main_parser.add_subparsers()
        >>> setup_init_parser(subparsers.add_parser("init", add_help=False))
        None
    """
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help=_("Show this help message and exit."),
    )
    parser.add_argument(
        "-cl",
        "--command-line",
        help=_("Add a command-line to the project."),
        action="store_true",
    )
    parser.add_argument(
        "-gh",
        "--github",
        "--GitHub",
        help=_("Configure the project for GitHub and push it."),
        action="store_true",
    )
    parser.add_argument(
        "-pp",
        "--pypi",
        "--PyPI",
        help=_(
            "Configure GitHub to publish package to PyPI. This imply `-gh`."
        ),
        action="store_true",
    )
    parser.add_argument(
        "-cc",
        "--codecov",
        "--CodeCov",
        help=_(
            "Configure GitHub to publish coverage report to CodeCov."
            " This imply `-gh`."
        ),
        action="store_true",
    )
    parser.add_argument(
        "-rd",
        "--readthedocs",
        "--ReadTheDocs",
        help=_(
            "Configure GitHub to publish documentation to ReadTheDocs."
            " This imply `-gh`."
        ),
        action="store_true",
    )
    parser.add_argument(
        "-pr",
        "--protect-repository",
        help=_(
            "Configure GitHub to protect branches and tags. This imply `-gh`."
        ),
        action="store_true",
    )
    parser.add_argument(
        "-ga",
        "--github-all",
        "--GitHub-all",
        help=_(
            "Full GitHub configuration."
            " This imply `-pp`, `-cc`, `rd`, and `-pr`."
        ),
        action="store_true",
    )
    project_directory_arg = cast(
        "CompleterAction",
        parser.add_argument(
            "project_directory",
            default=import_lazy("os").getcwd(),
            nargs="?",
            help=_("Directory in which to initialize the Python project."),
            metavar="PROJECT_DIRECTORY",
        ),
    )
    if (argcomplete := import_extra("argcomplete")) is not None:
        project_directory_arg.completer = argcomplete.DirectoriesCompleter()
