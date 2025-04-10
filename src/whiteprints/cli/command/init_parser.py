# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'init' subcommand."""

import importlib
from argparse import ArgumentParser
from pathlib import Path
from typing import Final

from whiteprints import _


__all__: Final = ["setup_init_parser"]


def setup_init_parser(parser: ArgumentParser) -> None:
    """Add a subparser to initialize a Python project.

    Example:
        >>> main_parser = ArgumentParser()
        >>> subparsers = main_parser.add_subparsers()
        >>> setup_init_parser(subparsers.add_parser("init"))
        None

    Args:
        subparser: the subparser to attach to
        parser: the main parser use to forward the `formatter_class`.
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
    project_directory_arg = parser.add_argument(
        "project_directory",
        default=str(Path.cwd()),
        nargs="?",
        help=_("Directory in which to initialize the Python project."),
        metavar="PROJECT_DIRECTORY",
    )
    completer = getattr(project_directory_arg, "completer", None)
    if completer is not None:
        completer = importlib.import_module(
            "argcomplete"
        ).DirectoriesCompleter()

    project_directory_arg = parser.add_argument(
        "copier_args",
        default=[],
        nargs="*",
        help=_("Additional arguments forwarded to each Copier invocations."),
        metavar="COPIER_ARGS",
    )
