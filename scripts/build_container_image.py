# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later

# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "click>=8.1.0",
#     "semver>=3.0.2",
#     "click>=8.1.0"
# ]
# ///

import datetime
import shutil
import subprocess  # nosec
from pathlib import Path

import click
from semver import Version


BASE_IMAGE = {
    "alpine": {
        "PYTHON_VERSION": "3.13",
        "BASE_OS": "alpine3.20",
        "DIGEST": ""
    },
    "debian": {
        "PYTHON_VERSION": "3.13",
        "BASE_OS": "slim-bookworm",
        "DIGEST": "",
    },
}


def run_command(command: str, args: list[str], *, capture_output: bool = True) -> str | None:
    """Run a git command using subprocess and return its output.

    Args:
        args: List of command-line arguments for git.

    Returns:
        The command output as a string.

    Raises:
        FileNotFoundError: If git executable is not found.
        subprocess.CalledProcessError: If the git command fails.
    """
    git_path = shutil.which(command)
    if git_path is None:
        raise FileNotFoundError(
          f"{command} executable not found. Ensure {command} is installed and in your PATH."
        )

    result = subprocess.run(  # nosec
        [git_path, *args],
        capture_output=capture_output,
        text=True,
        check=True,
        shell=False
    )
    if capture_output:
        return result.stdout.strip()


def get_version_tags(ref_prefix: str) -> list[Version]:
    """Retrieve and parse version tags from the Git repository using subprocess.

    Args:
        ref_prefix: The prefix for tag references (e.g., "refs/tags/").

    Returns:
        A list of parsed Version objects.
    """
    tags = run_command("git", ["tag", "--list"]).splitlines()
    version_tags = []
    prefix_len = len(ref_prefix)
    all_tag_refs = (ref for ref in tags if ref.startswith(ref_prefix))
    for tag_ref in all_tag_refs:
        try:
            version_tag = Version.parse(tag_ref[prefix_len:])
            version_tags.append(version_tag)
        except ValueError:
            continue

    return version_tags


def initialize_latest_version(version_tags: list[Version]) -> Version:
    """Initialize the latest version from the list of version tags.

    Args:
        version_tags: The list of parsed Version objects.

    Returns:
        The latest version or Version(0, 0, 0) if no tags are found.
    """
    if version_tags:
        return sorted(version_tags)[-1]

    return Version(0, 0, 0)


def get_current_commit_hash() -> str:
    """Retrieve the current commit hash from the Git repository using subprocess.

    Returns:
        The commit hash as a string.
    """
    try:
        commit_hash = run_command("git", ["rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        commit_hash = ""

    return commit_hash


def build_container(
    context_path: Path,
    *,
    file: Path,
    tags: list[str],
    build_args: dict[str, str],
    extra_args: list[str],
) -> None:
    """Build a container image using Podman.

    Args:
        context_path: Path to the build context directory.
        file: Path to the Containerfile.
        tags: List of image tags to apply.
        build_args: Dictionary of build arguments (key-value pairs).
    """
    build_command = [
        "build",
        "--file",
        str(file),
    ]
    for tag in tags:
        build_command.extend(("--tag", tag))

    for key, value in build_args.items():
        build_command.extend(["--build-arg", f"{key}={value}"])

    build_command.extend(extra_args)
    build_command.append(str(context_path))
    run_command("podman", build_command, capture_output=False)


def build_container_image(additional_tag: list[str], os: str, extra_args: list[str]) -> None:
    now = datetime.datetime.now(datetime.UTC)

    ref_prefix = "refs/tags/v"

    package = {
        "VERSION": initialize_latest_version(
            get_version_tags(ref_prefix)
        ),
    }
    name = "whiteprints"
    base_image = BASE_IMAGE.get(os, {})
    default_tag = f"{name}:{package['VERSION']}-py{base_image['PYTHON_VERSION']}-{base_image['BASE_OS']}"
    all_tags = [default_tag, *(f"{name}:{tag}" for tag in additional_tag)]

    build_container(
        context_path=Path(),
        file=Path() / "container" / f"Containerfile.{os}",
        tags=all_tags,
        build_args={
            **base_image,
            **package,
            "UV_COMPILE_BYTECODE": 1,
            "REVISION": get_current_commit_hash(),
            "BUILD_DATE": now.isoformat(),
        },
        extra_args=list(extra_args),
    )


@click.command(context_settings={"ignore_unknown_options": True})
@click.option(
    "--additional-tag",
    "-t",
    multiple=True,
    help="Additional tag(s) to apply to the built container image.",
)
@click.argument(
    "os",
    type=click.Choice([*BASE_IMAGE.keys(), "all"], case_sensitive=False),
)
@click.argument(
    "extra_args",
    nargs=-1,
    type=click.UNPROCESSED,
)
def main(additional_tag: list[str], os: str, extra_args: list[str]) -> None:
    """Main function to build a container image using the Podman Docker client.

    This function retrieves version tags from a Git repository, initializes
    the latest version, and builds a container image using specified base image
    settings. It also sets build arguments such as the current commit hash and
    build date.
    """
    if os == "all":
        for specific_os in BASE_IMAGE:
            build_container_image(
                additional_tag,
                os=specific_os,
                extra_args=extra_args,
            )
    else:
        build_container_image(
            additional_tag,
            os=specific_os,
            extra_args=extra_args,
        )


if __name__ == "__main__":
    main()
