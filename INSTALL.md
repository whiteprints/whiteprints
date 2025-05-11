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

If you don't have uv installed, you can have a look at the uv
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

# ✨ Installing optional features

By default, the CLI is installed without any optional dependencies. This keeps
the installation minimal and avoids pulling in unnecessary packages.

However, you can enable additional features by installing *extras*, which
provide support for:

- Colored terminal output
- Shell autocompletion
- Automatic loading of `.env` files

To install the CLI with extras, use the following syntax:

```
uv tool install whiteprints[qol,color]
```

In the example above:

- `color` enables ANSI-colored output in help messages and errors.
- `qol` (Quality of Life) enables shell autocompletion and `.env` file
  autoloading , and smart handling of config and cache directories based on
  your operating system.

> **Note:** Installing extras will increase the number of dependencies and may
> slightly affect CLI startup performance. Only enable the extras you actually
> need.

[GitHub]: https://github.com
[git]: https://git-scm.com/

[PyPA]: https://www.pypa.io/en/latest/
[pip]: https://pip.pypa.io/en/stable
[package]: https://pypi.org/project/whiteprints
[uv]: https://docs.astral.sh/uv/
[pipx]: https://pipx.pypa.io/stable/

# 📚 Further Reading

For additional information on source installation see [PyPA]'s guide:
[installing Packages](https://packaging.python.org/en/latest/tutorials/installing-packages).

For more details on how Python extras work, see the official guide:
[Installing Extras – Python Packaging User Guide](https://packaging.python.org/en/latest/tutorials/installing-packages/#installing-extras)

