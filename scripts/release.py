# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pygit2>=1.15.1",
#     "semver>=3.0.2",
#     "click>=8.1.0"
# ]
# ///
"""Version Bump Utility.

This module provides a CLI tool for bumping semantic version numbers in a Git
repository. It supports patch, minor, major, pre-release, and finalization
bumps.

Example usage:
    python bump_version.py patch
    python bump_version.py pre-release --pre-id beta
    python bump_version.py finalize
"""

from pathlib import Path
from typing import List, Optional

import click
from pygit2 import Repository, enums
from semver import Version


def create_tag(repo: Repository, *, version: Version, message: str) -> None:
    """Create a new tag in the repository."""
    tag_name = f"v{version}"
    repo.create_tag(
        tag_name,
        repo.head.target,
        enums.ObjectType.COMMIT,
        repo.default_signature,
        message,
    )


def gitflow_action(
    repo: Repository,
    *,
    new_version: Version,
    tag: bool,
    message: str,
) -> None:
    """Handle git-flow actions based on flags.

    Args:
        new_version: The new version to use with git-flow commands.
        start_flow: Whether to start a Gitflow release branch.
        finish_flow: Whether to finish the Gitflow release branch.
    """
    if tag:
        create_tag(
            repo,
            version=new_version,
            message=message or f"Finalize release {new_version}",
        )


def get_version_tags(repo: Repository, *, ref_prefix: str) -> List[Version]:
    """Retrieve and parse version tags from the repository.

    Args:
        repo: The pygit2 repository object.
        ref_prefix: The prefix for tag references (e.g., "refs/tags/").

    Returns:
        A list of parsed Version objects.
    """
    prefix_len = len(ref_prefix)
    tags = repo.listall_references()
    version_tags = []

    all_tag_refs = (ref for ref in tags if ref.startswith(ref_prefix))
    for tag_ref in all_tag_refs:
        try:
            version_tag = Version.parse(tag_ref[prefix_len:])
            version_tags.append(version_tag)
        except ValueError:
            continue

    return version_tags


def initialize_latest_version(version_tags: List[Version]) -> Version:
    """Initialize the latest version from the list of version tags.

    Args:
        version_tags: The list of parsed Version objects.

    Returns:
        The latest version or Version(0, 0, 0) if no tags are found.
    """
    if version_tags:
        return sorted(version_tags)[-1]

    return Version(0, 0, 0)


@click.command(
    help=(
        """
    Bump the version using semantic versioning.

    Available bump types:

        - patch: Increment the patch version (x.y.Z).

        - minor: Increment the minor version (x.Y.z).

        - major: Increment the major version (X.y.z).

        - pre-release: Add or update a pre-release tag (e.g., alpha, beta).

        - finalize: Remove the pre-release tag for a stable version.

    Example usage:
      python bump_version.py patch
      python bump_version.py pre-release --pre-id beta
      python bump_version.py finalize
"""
    )
)
@click.argument(
    "bump_type",
    type=click.Choice(
        ["patch", "minor", "major", "pre-release", "finalize"],
        case_sensitive=False,
    ),
    required=False,
)
@click.option(
    "--pre-id",
    default="rc",
    help=(
        "Pre-release identifier (e.g., alpha, beta, rc)."
        " Used only with pre-release bump."
    ),
)
@click.option("--tag", is_flag=True, help="Add a version tag.")
@click.option("--message", help="An optional message tag.")
def main(
    bump_type: str,
    pre_id: str,
    tag: bool,
    message: Optional[str],
) -> None:
    """Bump the project version based on the specified bump type.

    Args:
        bump_type:
            Type of version bump.
            Options are 'patch', 'minor', 'major', 'pre-release', 'finalize'.
        pre_id:
            Identifier for pre-release versions (e.g., alpha, beta, rc).
            Used only with 'pre-release' bump.
        tag:
            Add a version tag.
        message:
            an optional tag message.

    The script detects the latest Git tag, applies the specified bump,
    and handles pre-release and finalization logic.
    """
    repo = Repository(str(Path()))

    ref_prefix = "refs/tags/v"

    version_tags = get_version_tags(repo, ref_prefix=ref_prefix)
    latest_version = initialize_latest_version(version_tags)

    bump_actions = {
        "patch": latest_version.bump_patch,
        "minor": latest_version.bump_minor,
        "major": latest_version.bump_major,
        "pre-release": lambda: latest_version.bump_prerelease(token=pre_id),
        "finalize": latest_version.finalize_version,
    }
    bump_function = bump_actions.get(bump_type, lambda: latest_version)
    new_version = bump_function()

    click.echo(f"Release: {new_version}")
    gitflow_action(
        repo,
        tag=tag,
        new_version=new_version,
        message=message or "",
    )


if __name__ == "__main__":
    main()
