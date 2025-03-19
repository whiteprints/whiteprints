# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'init' subcommand."""

import importlib
from argparse import Action, ArgumentParser
from pathlib import Path

from whiteprints import _


def init_parser(subparser: Action, parser: ArgumentParser) -> None:
    """Add a subparser to initialize a Python project."""
    add_parser = getattr(subparser, "add_parser", None)
    if add_parser is None:
        return

    parser = add_parser(
        "init",
        formatter_class=parser.formatter_class,
        description=_("Initialize a Python project."),
        help=_("Initialize a Python project."),
        exit_on_error=False,
        add_help=False,
    )
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
            " This imply `--github`."
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
            "Configure GitHub to protect branches and tags. "
            "This imply `--github`."
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
    with importlib.import_module("contextlib").suppress(ModuleNotFoundError):
        project_directory_arg.__dict__["completer"] = importlib.import_module(
            "argcomplete"
        ).DirectoriesCompleter()
