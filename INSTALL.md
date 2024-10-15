<!--
SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>

SPDX-License-Identifier: CC-BY-NC-SA-4.0
-->

# ⚙️ Installation

We recommend installing the [package] using [uv] or [pipx].

## Using uv (recommended)

To [package] with [uv] run:

```
uv tool install whiteprints
```

If you don't have uv install, you can have a look at the uv
[installation guide](https://docs.astral.sh/uv/getting-started/installation/).

## Using pipx

You can also install the [package] with [pipx] by running.

```
pipx install whiteprints
```

You can install [pipx] following the [installation guide](https://pipx.pypa.io/stable/installation/)

## From PyPI

To install the [package] from [PyPI] run

```console
pip install whiteprints
```

Do not forget that you should probably not install the package as root but as a
user. Moreover you should also install the package in a dedicated virtual
environment (which is exactly what [uv] and [pipx] are doing).

[PyPI]: https://pypi.org/

## From source

To install with [pip] from [GitHub] run the command:

```console
pip install git+ssh://git@github.com/whiteprints/whiteprints
```

The same recommendations made for PyPI installation apply.

[GitHub]: https://github.com
[git]: https://git-scm.com/

For additional information on source installation see [PyPA]'s guide:
[installing Packages](https://packaging.python.org/en/latest/tutorials/installing-packages).

[PyPA]: https://www.pypa.io/en/latest/
[pip]: https://pip.pypa.io/en/stable
[package]: https://pypi.org/project/whiteprints
[uv]: https://docs.astral.sh/uv/
[pipx]: https://pipx.pypa.io/stable/
