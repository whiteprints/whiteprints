# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project."""

import sys
from collections.abc import Iterable
from pathlib import Path
from subprocess import CalledProcessError  # nosec
from typing import Final, TypedDict

from click import ClickException

from whiteprints.cli.init_interface import InitKwargs
from whiteprints.copier_run import Copier


if sys.version_info >= (3, 11):
    from typing import Required, Unpack
else:
    from typing_extensions import Required, Unpack


__all__: Final = ["CopierCopyError", "init"]


WHITEPRINTS_TEMPLATE_CONTEXT_VERSION: Final = "0.2.1"
"""The whiteprints-template-context version pin."""


class _FeatureRepository(TypedDict):
    """Feature dictionnary interface."""

    pypi: Required[str]
    codecov: Required[str]
    readthedocs: Required[str]
    protect_repository: Required[str]


FEATURE_REPOSITORY = _FeatureRepository(
    pypi="gh:whiteprints/template-github-publish-pypi.git",
    codecov="gh:whiteprints/template-github-codecov.git",
    readthedocs="gh:whiteprints/template-github-readthedocs.git",
    protect_repository="gh:whiteprints/template-github-protect-repository.git",
)
"""A mapping from a feature name to its template repository."""


class CopierCopyError(ClickException):
    """An error occured while creating the project."""

    def __init__(self) -> None:
        """Create an exception instance."""
        super().__init__("Project creation failed.")


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
    for feature, repository in FEATURE_REPOSITORY.items():
        if _should_add(feature, cli_kwargs=kwargs):  # pragma: no cover
            copier.copy(
                [
                    # There seems to be a bug in pyright as of 2024/10/19
                    # repository is guaranteed to be a string, as shown
                    # in the TypedDict _FeatureRepository...
                    repository,  # type: ignore[reportPropertyTypeMismatch]
                    project_directory,
                    *copier_args,
                ],
                context=[
                    "whiteprints-template-context=="
                    + WHITEPRINTS_TEMPLATE_CONTEXT_VERSION
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
                "whiteprints-template-context=="
                + WHITEPRINTS_TEMPLATE_CONTEXT_VERSION
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
            "whiteprints-template-context=="
            + WHITEPRINTS_TEMPLATE_CONTEXT_VERSION
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
                "whiteprints-template-context=="
                + WHITEPRINTS_TEMPLATE_CONTEXT_VERSION
            ],
            trust=True,
        )

    add_github(
        copier,
        copier_args=copier_args,
        project_directory=project_directory,
        **kwargs,
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
    except CalledProcessError as process_error:
        raise CopierCopyError from process_error
