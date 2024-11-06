# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'init' command."""

import importlib
import sys
from collections.abc import Iterable
from pathlib import Path

import rich_click as click

from whiteprints.cli.init_interface import InitKwargs
from whiteprints.loc import _


if sys.version_info < (3, 11):
    from typing_extensions import Unpack
else:
    from typing import Unpack


@click.command(
    name=_("init"),
    help=_(
        """Initialize a Python project.

COPIER_ARGS are additional arguments forwarded to each copier command line
invocation.
"""
    ),
    context_settings={
        "ignore_unknown_options": True,
    },
)
@click.argument(
    "project_directory",
    default=".",
    type=click.Path(
        exists=False,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        executable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
    ),
)
@click.argument("copier_args", nargs=-1, type=click.UNPROCESSED)
@click.option(
    "-cl",
    "--command-line",
    help=_("Add a command-line to the project"),
    type=bool,
    default=False,
    is_flag=True,
)
@click.option(
    "-gh",
    "--github",
    "--GitHub",
    help=_("Push to GitHub."),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-pp",
    "--pypi",
    "--PyPI",
    help=_(
        "Configure GitHub to publish package to PyPI. This imply `--github`."
    ),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-cc",
    "--codecov",
    "--CodeCov",
    help=_(
        "Configure GitHub to publish coverage to CodeCov."
        " This imply `--github`."
    ),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-rd",
    "--readthedocs",
    "--ReadTheDocs",
    help=_(
        "Configure GitHub to publish documentation to ReadTheDocs."
        " This imply `--github`."
    ),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-pr",
    "--protect-repository",
    help=_(
        "Configure GitHub to protect branches and tags. This imply `--github`."
    ),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-ga",
    "--github-all",
    help=_(
        "This imply "
        "`--github`, `--codecov`, `--pypi` and `--protect-repository`."
    ),
    type=bool,
    default=False,
    show_default=True,
    is_flag=True,
)
def init(
    project_directory: Path,
    copier_args: Iterable[str],
    **kwargs: Unpack[InitKwargs],
) -> None:
    """Initialize a python project.

    Args:
        project_directory: directory the new project will be created.
        copier_args: arguments forwarded to copier.
        kwargs: the command line flags.
    """
    importlib.import_module(
        "whiteprints.cli.init",
        __package__,
    ).init(
        project_directory=project_directory,
        copier_args=copier_args,
        **kwargs,
    )
