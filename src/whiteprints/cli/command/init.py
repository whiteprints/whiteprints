# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project."""

import importlib
import os
import sys
from argparse import Namespace
from collections.abc import Iterable
from subprocess import CalledProcessError  # nosec
from typing import Final, TypedDict

from whiteprints import _
from whiteprints.libuv.copier import Copier


if sys.version_info >= (3, 11):
    from typing import Required
else:
    from typing_extensions import Required


__all__: Final = ["init"]


WHITEPRINTS_TEMPLATE_CONTEXT_VERSION: Final = "0.6.0"
"""The whiteprints-template-context version pin."""


class InitKwargs(TypedDict):
    """The 'init' command line arguments."""

    command_line: bool
    github: bool
    pypi: bool
    codecov: bool
    readthedocs: bool
    protect_repository: bool
    github_all: bool


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
    init_kwargs: InitKwargs,
) -> None:
    """Update the project to add GitHub functionalities.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        init_kwargs: the command line flags.
    """
    for feature, repository in FEATURE_REPOSITORY.items():
        if _should_add(feature, cli_kwargs=init_kwargs):  # pragma: no cover
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


def _require_github(init_kwargs: InitKwargs) -> bool:
    """Check if the project requires a GitHub configuration.

    Args:
        init_kwargs: the command line flags.

    Returns:
        True if the project requires a GitHub configuration, False otherwise.
    """
    return (
        init_kwargs["pypi"]
        or init_kwargs["codecov"]
        or init_kwargs["readthedocs"]
        or init_kwargs["protect_repository"]
    )


def add_github(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    init_kwargs: InitKwargs,
) -> None:
    """Update the project to add GitHub functionalities.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        init_kwargs: the command line flags.
    """
    if (  # pragma: no cover
        init_kwargs["github"]
        or init_kwargs["github_all"]
        or _require_github(init_kwargs)
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
        init_kwargs=init_kwargs,
    )


def create_project(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    init_kwargs: InitKwargs,
) -> None:
    """Initialize a python project.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        init_kwargs: the command line flags.
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
    if init_kwargs["command_line"]:  # pragma: no cover
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
        init_kwargs=init_kwargs,
    )


def init(namespace: Namespace) -> None:
    """Initialize a python project.

    Args:
        namespace: the arguments namespace.
    """
    copier = Copier()
    project_directory_str = str(namespace.project_directory)

    try:
        create_project(
            copier,
            copier_args=namespace.copier_args,
            project_directory=project_directory_str,
            init_kwargs={
                "command_line": namespace.command_line,
                "github": namespace.github,
                "pypi": namespace.pypi,
                "codecov": namespace.codecov,
                "readthedocs": namespace.readthedocs,
                "protect_repository": namespace.protect_repository,
                "github_all": namespace.github_all,
            },
        )
    except CalledProcessError:
        importlib.import_module("whiteprints", __package__).stderr().print(
            _("[red]Project creation failed[/]")
        )
        logger = importlib.import_module("logging").getLogger(__name__)
        logger.exception("Exception caught", stack_info=True)
        sys.exit(os.EX_SOFTWARE)
