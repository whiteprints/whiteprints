# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Initialize a project using pure logic for testable copy operations."""

import importlib
import logging
import os
import sys
from argparse import Namespace
from collections.abc import Iterable
from dataclasses import dataclass
from subprocess import CalledProcessError  # nosec
from typing import Final

from whiteprints import _, has_extra
from whiteprints.cli import robust_print


WHITEPRINTS_TEMPLATE_CONTEXT_VERSION: Final = "0.6.0"
"""The whiteprints-template-context version pin."""

# Define the repository mapping from feature names to copier templates
_GITHUB_EXTRAS: Final[dict[str, str]] = dict(
    zip(
        ["pypi", "codecov", "readthedocs", "protect_repository"],
        (
            "gh:whiteprints/template-github-publish-pypi.git",
            "gh:whiteprints/template-github-codecov.git",
            "gh:whiteprints/template-github-readthedocs.git",
            "gh:whiteprints/template-github-protect-repository.git",
        ),
        strict=False,
    )
)


@dataclass(frozen=True)
class CopyOp:
    """Descriptor for a copier operation, pure and testable."""

    repo: str
    dest: str
    args: Iterable[str]
    context: Iterable[str]
    trust: bool


def build_github_ops(
    project_directory: str,
    copier_args: Iterable[str],
    init_kwargs: dict[str, bool],
    context: Iterable[str],
) -> list[CopyOp]:
    """Build copy operations for GitHub core and feature extras.

    Args:
        project_directory: target directory
        copier_args: extra args for copier
        init_kwargs: flags for github, github_all, extras
        context: the shared context list

    Returns:
        CopyOp list for GitHub actions
    """
    ops: list[CopyOp] = []

    # Determine if any GitHub integration is needed
    github_core = (
        init_kwargs.get("github", False)
        or init_kwargs.get("github_all", False)
        or any(init_kwargs.get(f, False) for f in _GITHUB_EXTRAS)
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
        if init_kwargs.get("github_all") or init_kwargs.get(feature):
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
    init_kwargs: dict[str, bool],
) -> list[CopyOp]:
    """Build a list of CopyOp instances based on feature flags.

    Args:
        project_directory: target directory for templates
        copier_args: extra arguments to forward to copier
        init_kwargs: boolean flags for each feature

    Returns:
        a list of CopyOp objects describing the copy operations to perform.
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
    if init_kwargs.get("command_line"):
        ops.append(
            CopyOp(
                repo="gh:whiteprints/template-rich-click.git",
                dest=project_directory,
                args=copier_args,
                context=context,
                trust=True,
            )
        )

    ops.extend(
        build_github_ops(project_directory, copier_args, init_kwargs, context)
    )
    return ops


def init(namespace: Namespace) -> None:
    """Initialize a python project by executing all copy operations."""
    copier = importlib.import_module("whiteprints.libuv.copier").Copier()
    project_directory = str(namespace.project_directory)

    # Gather boolean flags into a dict for build_copy_ops
    init_kwargs = {
        "command_line": bool(namespace.command_line),
        "github": bool(namespace.github),
        "pypi": bool(namespace.pypi),
        "codecov": bool(namespace.codecov),
        "readthedocs": bool(namespace.readthedocs),
        "protect_repository": bool(namespace.protect_repository),
        "github_all": bool(namespace.github_all),
    }

    try:
        for op in build_copy_ops(
            project_directory,
            namespace.copier_args,
            init_kwargs,
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
            file=sys.stderr,
        )
        logger = logging.getLogger(__name__)
        logger.exception(
            "Exception caught while running Copier",
            stack_info=True,
        )
        sys.exit(os.EX_SOFTWARE)
