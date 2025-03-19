# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project."""

import importlib
import os
import sys
from argparse import Namespace
from typing import Final, TypedDict

from whiteprints import _


__all__: Final = ["init"]


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

    pypi: str
    codecov: str
    readthedocs: str
    protect_repository: str


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
            importlib.import_module("copier.main").Worker(
                src_path=repository,
                dst_path=project_directory,
                unsafe=True,
            ).run_copy()


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
        importlib.import_module("copier.main").Worker(
            src_path="gh:whiteprints/template-github.git",
            dst_path=project_directory,
            unsafe=True,
        ).run_copy()

    add_github_functionalities(
        project_directory=project_directory,
        init_kwargs=init_kwargs,
    )


def create_project(
    *,
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
    importlib.import_module("copier.main").Worker(
        src_path="gh:whiteprints/template-python.git",
        dst_path=project_directory,
        unsafe=True,
    ).run_copy()
    if init_kwargs["command_line"]:  # pragma: no cover
        importlib.import_module("copier.main").Worker(
            src_path="gh:whiteprints/template-rich-click.git",
            dst_path=project_directory,
            unsafe=True,
        ).run_copy()

    add_github(
        project_directory=project_directory,
        init_kwargs=init_kwargs,
    )


def init(namespace: Namespace) -> None:
    """Initialize a python project.

    Args:
        namespace: the argument parser namespace.
    """
    logger = importlib.import_module("logging").getLogger(__name__)
    logger.debug("Project creation started")
    copier_errors = importlib.import_module("copier.errors")
    try:
        project_directory_str = namespace.project_directory
        create_project(
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
        logger.debug("Project creation succeed")
    except copier_errors.CopierAnswersInterrupt as copier_answer_interrupt:
        importlib.import_module("whiteprints", __package__).stderr().print(
            _("[red]Execution stopped by user[/]")
        )
        logger.debug(
            "Copier stopped by user.",
            extra={"copier_answer_interrupt": str(copier_answer_interrupt)},
        )
        sys.exit(importlib.import_module("signal").SIGINT)
    except copier_errors.CopierError:
        logger = importlib.import_module("logging").getLogger(__name__)
        logger.exception("Copier Error", stack_info=True)
        sys.exit(os.EX_SOFTWARE)
