# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project using pure logic for testable copy operations."""

import importlib
import logging
from argparse import Namespace
from collections.abc import Iterable
from dataclasses import dataclass
from subprocess import CalledProcessError  # nosec
from typing import Final

from whiteprints import _, has_extra
from whiteprints.cli import PosixExitCode, robust_print


WHITEPRINTS_TEMPLATE_CONTEXT_VERSION: Final = "0.6.0"
"""The whiteprints-template-context version pin."""

_GITHUB_EXTRAS: Final = {
    "pypi": "gh:whiteprints/template-github-publish-pypi.git",
    "codecov": "gh:whiteprints/template-github-codecov.git",
    "readthedocs": "gh:whiteprints/template-github-readthedocs.git",
    "protect_repository": (
        "gh:whiteprints/template-github-protect-repository.git"
    ),
}
"""Define the repository mapping from feature names to copier templates."""


@dataclass(frozen=True, slots=True)
class CopyOp:
    """Descriptor for a copier operation."""

    repo: str
    dest: str
    args: Iterable[str]
    context: Iterable[str]
    trust: bool


def build_github_ops(
    project_directory: str,
    copier_args: Iterable[str],
    namespace: Namespace,
    context: Iterable[str],
) -> list[CopyOp]:
    """Build copy operations for GitHub core and feature extras.

    Args:
        project_directory: target directory
        copier_args: extra args for copier
        namespace: flags for github, github_all, extras.
        context: the shared context list

    Returns:
        CopyOp list for GitHub actions


    Example:
        >>> from argparse import Namespace
        >>>
        >>> ns = Namespace(
        ...     github=True,
        ...     github_all=False,
        ...     pypi=False,
        ...     codecov=False,
        ...     readthedocs=False,
        ...     protect_repository=False
        ... )
        >>>
        >>> ops = build_github_ops('proj', [], ns, ['ctx'])
        >>> [o.repo for o in ops]
        ['gh:whiteprints/template-github.git']
    """
    ops: list[CopyOp] = []

    # Determine if any GitHub integration is needed
    github_core = (
        bool(namespace.github)
        or bool(namespace.github_all)
        or any(bool(getattr(namespace, f)) for f in _GITHUB_EXTRAS)
    )
    if github_core:
        ops.append(
            CopyOp(
                repo="gh:whiteprints/template-github.git",
                dest=project_directory,
                args=copier_args,
                context=context,
                trust=True,
            )
        )

    # Add each extra feature template if requested or global flag
    for feature, repo in _GITHUB_EXTRAS.items():
        if bool(namespace.github_all) or bool(getattr(namespace, feature)):
            ops.append(
                CopyOp(
                    repo=repo,
                    dest=project_directory,
                    args=copier_args,
                    context=context,
                    trust=True,
                )
            )
    return ops


def build_copy_ops(
    project_directory: str,
    copier_args: Iterable[str],
    namespace: Namespace,
) -> list[CopyOp]:
    """Build a list of CopyOp instances based on feature flags.

    Args:
        project_directory: target directory for templates
        copier_args: extra arguments to forward to copier
        namespace: boolean flags for each feature

    Returns:
        a list of CopyOp objects describing the copy operations to perform.

    Example:
        >>> from argparse import Namespace
        >>>
        >>> ns = Namespace(
        ...     command_line=True,
        ...     github=False,
        ...     github_all=False,
        ...     pypi=False,
        ...     codecov=False,
        ...     readthedocs=False,
        ...     protect_repository=False
        ... )
        >>>
        >>> ops = build_copy_ops('proj', [], ns)
        >>> [o.repo for o in ops]
        [..., 'gh:whiteprints/template-rich-click.git']
    """
    ops: list[CopyOp] = []
    context = [
        f"whiteprints-template-context=={WHITEPRINTS_TEMPLATE_CONTEXT_VERSION}"
    ]

    # Base Python template
    ops.append(
        CopyOp(
            repo="gh:whiteprints/template-python.git",
            dest=project_directory,
            args=copier_args,
            context=context,
            trust=True,
        )
    )

    # Optional CLI support
    if bool(namespace.command_line):
        ops.append(
            CopyOp(
                repo="gh:whiteprints/template-rich-click.git",
                dest=project_directory,
                args=copier_args,
                context=context,
                trust=True,
            )
        )

    # Optional GitHub and GitHub extras support
    ops.extend(
        build_github_ops(project_directory, copier_args, namespace, context)
    )
    return ops


def init(namespace: Namespace) -> None:
    """Initialize a python project by executing all copy operations."""
    copier = importlib.import_module("whiteprints.libuv.copier").Copier()
    project_directory = str(namespace.project_directory)

    try:
        for op in build_copy_ops(
            project_directory,
            namespace.copier_args,
            namespace,
        ):
            copier.copy(
                [op.repo, op.dest, *op.args],
                context=op.context,
                trust=op.trust,
            )
    except CalledProcessError:
        error_message = _("Project creation failed")
        robust_print(
            (
                f"[red]{error_message}[/]"
                if has_extra("rich")
                else error_message
            ),
            file=importlib.import_module("sys").stderr,
        )
        logger = logging.getLogger(__name__)
        logger.exception(
            "Exception caught while running Copier",
            stack_info=True,
        )
        PosixExitCode.INTERNAL_SOFTWARE_ERROR.exit()
