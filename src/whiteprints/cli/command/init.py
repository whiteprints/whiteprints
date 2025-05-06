# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project."""

import importlib
import sys
from argparse import Namespace
from collections.abc import Iterable
from subprocess import CalledProcessError  # nosec
from typing import Final, Literal, TypedDict, get_args

from whiteprints import _, has_extra
from whiteprints.cli import robust_print
from whiteprints.libuv.copier import Copier


__all__: Final = ["init"]


WHITEPRINTS_TEMPLATE_CONTEXT_VERSION: Final = "0.6.0"
"""The whiteprints-template-context version pin."""

_Feature = Literal["pypi", "codecov", "readthedocs", "protect_repository"]
"""Feature list."""

_FEATURE_REPOSITORY: Final[dict[_Feature, str]] = dict(
    zip(
        get_args(_Feature),
        (
            "gh:whiteprints/template-github-publish-pypi.git",
            "gh:whiteprints/template-github-codecov.git",
            "gh:whiteprints/template-github-readthedocs.git",
            "gh:whiteprints/template-github-protect-repository.git",
        ),
        strict=False,
    )
)
"""A mapping from a feature name to its template repository."""


class _InitKwargs(TypedDict):
    """The 'init' command line arguments."""

    command_line: bool
    github: bool
    pypi: bool
    codecov: bool
    readthedocs: bool
    protect_repository: bool
    github_all: bool


def _should_add(feature: _Feature, cli_kwargs: _InitKwargs) -> bool:
    """Whether a GitHub feature should be added.

    Args:
        feature: the feature to add.
        cli_kwargs: the command-line key-value arguments.

    Returns:
        True if the feature should be added, False otherwise.

    Example:
        >>> _should_add(
        >>>     "pypi",
        >>>     _InitKwargs(
        >>>         command_line=False,
        >>>         github=False,
        >>>         pypi=False,
        >>>         codecov=False,
        >>>         readthedocs=False,
        >>>         protect_repository=False,
        >>>         github_all=True,
        >>>     ),
        >>> )
        True
        >>> _should_add(
        >>>     "pypi",
        >>>     _InitKwargs(
        >>>         command_line=False,
        >>>         github=False,
        >>>         pypi=True,
        >>>         codecov=False,
        >>>         readthedocs=False,
        >>>         protect_repository=False,
        >>>         github_all=False,
        >>>     ),
        >>> )
        True
        >>> _should_add(
        >>>     "pypi",
        >>>     _InitKwargs(
        >>>         command_line=False,
        >>>         github=False,
        >>>         pypi=False,
        >>>         codecov=False,
        >>>         readthedocs=False,
        >>>         protect_repository=False,
        >>>         github_all=False,
        >>>     ),
        >>> )
        False
    """
    return cli_kwargs.get("github_all") or cli_kwargs[feature]


def add_github_functionalities(
    copier: Copier,
    *,
    copier_args: Iterable[str],
    project_directory: str,
    init_kwargs: _InitKwargs,
) -> None:
    """Update the project to add GitHub functionalities.

    Args:
        copier: a copier manager.
        copier_args: additional arguments forwarded to copier.
        project_directory: directory where the new project will be created.
        init_kwargs: the command line flags.
    """
    for feature, repository in _FEATURE_REPOSITORY.items():
        if _should_add(feature, cli_kwargs=init_kwargs):  # pragma: no cover
            copier.copy(
                [
                    repository,
                    project_directory,
                    *copier_args,
                ],
                context=[
                    "whiteprints-template-context=="
                    + WHITEPRINTS_TEMPLATE_CONTEXT_VERSION
                ],
                trust=True,
            )


def _require_github(init_kwargs: _InitKwargs) -> bool:
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
    init_kwargs: _InitKwargs,
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
    init_kwargs: _InitKwargs,
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
        error_message = _("Project creation failed")
        robust_print(
            (
                f"[red]{error_message}[/]"
                if has_extra("rich")
                else error_message
            ),
            file=sys.stderr,
        )
        logger = importlib.import_module("logging").getLogger(__name__)
        logger.exception(
            "Exception caught while running Copier",
            stack_info=True,
        )
        sys.exit(importlib.import_module("os").EX_SOFTWARE)
