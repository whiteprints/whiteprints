<!--
SPDX-FileCopyrightText: © 2024 The Whiteprints authors and contributors <whiteprints@pm.me>

SPDX-License-Identifier: CC-BY-NC-SA-4.0
-->

# 🛠️ Codebase Overview

The project is hosted on [https://github.com/whiteprints/whiteprints.git](https://github.com/whiteprints/whiteprints.git).

It is organised as follow.

## Files and directories

Here is a list of important resources for contributors:

- The licences: located in the `LICENCES/` directory.
- The project source code: located in the `src/` directory.
- The tests: located in the `tests/` directory.
- The documentation source code: located in the `docs/` directory.
- `tox.ini` contains [Tox]'s configuration
- `pyproject.toml` contains the [project metadata] and the [build system]

[project metadata]: https://peps.python.org/pep-0621/
[build system]: https://peps.python.org/pep-0518/

## Tools

The project relies on the following tools for development:

- [pip-audit]: used to find vulnerabilities in the supply chain.
- [pre-commit]: used to identifying simple issues before submission.
- [pyright]: used for type checking and as [LSP].
- [reuse]: check the licenses compliance.
- [ruff]: check and fix the Python's code format and syntax.
- [cyclonedx-bom]: generate a [bill of material] of the supply chain.
- [tox]: orchestrate tools and tests.

[pip-audit]: https://github.com/pypa/pip-audit
[pre-commit]: https://pre-commit.com/
[pyright]: https://microsoft.github.io/pyright/
[reuse]: https://reuse.software/
[ruff]: https://docs.astral.sh/ruff/
[cyclonedx-bom]: https://cyclonedx-bom-tool.readthedocs.io/en/latest/
[LSP]: https://en.wikipedia.org/wiki/Language_Server_Protocol
[bill of material]: https://en.wikipedia.org/wiki/Software_supply_chain

You may install all the tools using [uv]:

```console
uv tool install pip-audit
uv tool install pre-commit --with "pre-commit-uv"
uv tool install pyright
uv tool install reuse
uv tool install ruff
uv tool install cyclonedx-bom
uv tool install tox --with "tox-uv"
```

[Tox]: https://tox.wiki/en/stable/
