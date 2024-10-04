# SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The 'init' command.."""

from collections.abc import Iterable
from pathlib import Path
from subprocess import CalledProcessError  # nosec
from typing import TypedDict

import rich_click as click
from click import ClickException
from typing_extensions import Unpack

from whiteprints.copier_run import Copier
from whiteprints.loc import _


class CopierCopyError(ClickException):  # pragma: no cover
    """An error occured while creating the project."""

    def __init__(self) -> None:
        """Create an exception instance."""
        super().__init__("Project creation failed.")


class InitKwargs(TypedDict):
    """The 'init' command line arguments."""

    command_line: bool
    github: bool
    pypi: bool
    codecov: bool
    readthedocs: bool
    protect_repository: bool
    github_all: bool


def _should_add(feature: str, cli_kwargs: InitKwargs) -> bool:
    """Whether a GitHub feature should be added.

    Args:
        feature: the feature to add.
        cli_kwargs: the command-line key-value arguments.

    Returns:
        True if the feature should be added, False otherwise.
    """
    return cli_kwargs.get(feature, False) or cli_kwargs["github_all"]


def add_github_functionalities(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    **kwargs: Unpack[InitKwargs],
) -> None:
    """Update the project to add GitHub functionalities.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        kwargs: the command line flags.
    """
    if _should_add("pypi", cli_kwargs=kwargs):  # pragma: no cover
        copier.copy(
            [
                "gh:whiteprints/template-github-publish-pypi.git",
                project_directory,
                *copier_args,
            ],
            context=[
                "jinja2_time",
            ],
            trust=True,
        )

    if _should_add("codecov", cli_kwargs=kwargs):  # pragma: no cover
        copier.copy(
            [
                "gh:whiteprints/template-github-codecov.git",
                project_directory,
                *copier_args,
            ],
            context=[
                "jinja2_time",
            ],
            trust=True,
        )

    if (  # pragma: no cover
        _should_add("protect_repository", cli_kwargs=kwargs)
    ):
        copier.copy(
            [
                "gh:whiteprints/template-github-protect-repository.git",
                project_directory,
                *copier_args,
            ],
            context=[
                "jinja2_time",
            ],
            trust=True,
        )


def _require_github(**kwargs: Unpack[InitKwargs]) -> bool:
    """Check if the project requires a GitHub configuration.

    Args:
        kwargs: the command line flags.

    Returns:
        True if the project requires a GitHub configuration, False otherwise.
    """
    return (
        kwargs["pypi"]
        or kwargs["codecov"]
        or kwargs["readthedocs"]
        or kwargs["protect_repository"]
    )


def add_github(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    **kwargs: Unpack[InitKwargs],
) -> None:
    """Update the project to add GitHub functionalities.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        kwargs: the command line flags.
    """
    if (  # pragma: no cover
        kwargs["github"] or kwargs["github_all"] or _require_github(**kwargs)
    ):
        copier.copy(
            [
                "gh:whiteprints/template-github.git",
                project_directory,
                *copier_args,
            ],
            context=[
                "license-expression",
                "jinja2_time",
                "copier-templates-extensions",
            ],
            trust=True,
        )

    add_github_functionalities(
        copier,
        copier_args=copier_args,
        project_directory=project_directory,
        **kwargs,
    )


def create_project(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    **kwargs: Unpack[InitKwargs],
) -> None:
    """Initialize a python project.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        kwargs: the command line flags.
    """
    copier.copy(
        [
            "gh:whiteprints/template-python.git",
            project_directory,
            *copier_args,
        ],
        context=[
            "license-expression",
            "jinja2_time",
            "copier-templates-extensions",
        ],
        trust=True,
    )
    if kwargs["command_line"]:  # pragma: no cover
        copier.copy(
            [
                "gh:whiteprints/template-rich-click.git",
                project_directory,
                *copier_args,
            ],
            context=[
                "jinja2_time",
            ],
            trust=True,
        )

    add_github(
        copier,
        copier_args=copier_args,
        project_directory=project_directory,
        **kwargs,
    )


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
        "Configure GitHub to publish package to PyPI."
        " This imply `--github`."
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
    "-p/-P",
    "--protect-repository/--no-protect-repository",
    help=_(
        "Configure GitHub to protect branches and tags."
        " This imply `--github`."
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

    Raises:
        CopierCopyError: An error happened while creating the project.
    """
    copier = Copier()
    project_directory_str = str(project_directory)

    try:
        create_project(
            copier,
            copier_args=copier_args,
            project_directory=project_directory_str,
            **kwargs,
        )
    except CalledProcessError as process_error:  # pragma: no cover
        raise CopierCopyError from process_error
