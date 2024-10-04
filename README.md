<!--
SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Whiteprints

![Whiteprints](docs/_static/banner.svg)
<div align="center">
    <p>
        <em>
            A Copier-based cookiecutter for creating Python projects managed by uv.
        </em>
    </p>
    <p>
        <a href="https://pypi.org/project/whiteprints"><img alt="PyPI - Project Version" src="https://img.shields.io/pypi/v/whiteprints.svg?logo=PyPI&logoColor=3775A9"/></a>
        <a href="https://www.python.org"><img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/whiteprints.svg?logo=Python&logoColor=ffd43b"/></a>
        <a href="https://spdx.org/licenses/GPL-3.0-or-later"><img alt="license badge" src="https://img.shields.io/badge/📝_License-GPL--3.0--or--later-4CAF50.svg"/></a>
        <a href="https://github.com/whiteprints/whiteprints/discussions"><img alt="GitHub Discussions" src="https://img.shields.io/github/discussions/whiteprints/whiteprints.svg?logo=GitHub"></a>
        <a href="https://spdx.dev/learn/areas-of-interest/licensing/"><img alt="SPDX Licensing" src="https://img.shields.io/badge/SPDX-licensing-0080FF.svg?logo=SPDX"/></a>
        <a href='https://readthedocs.org/projects/whiteprints/'><img src='https://readthedocs.org/projects/whiteprints/badge/?version=latest' alt='Documentation Status' /></a>
        <a href="https://www.contributor-covenant.org/version/2/1/code_of_conduct/"><img alt="contributor covenant badge" src="https://img.shields.io/badge/Contributor_Covenant-2.1-4BAAAA.svg?logo=contributorcovenant"/></a>
        <a href="https://codecov.io/gh/whiteprints/whiteprints" ><img src="https://codecov.io/gh/whiteprints/whiteprints/graph/badge.svg?token=YrFGtQ5D5F"/></a>
    </p>
</div>

## Table of contents

- [Background](#background)
- [Highlights](#highlights)
- [Install](#install)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [Licensing](#licensing)

## Background

whiteprints is a command line to generate [Python] projects managed by [uv].

This is currently for my personal use, the documentation needs to be vastly
improved. However if you like the project feel free to use it, ask me questions
and even contribute 😊.

## Highlights

- Managed by [uv]
- [Tox], [Pytest] and [Sphinx] for the development
- Template for [GitHub] with actions to publish to [PyPI], [ReadTheDocs] and
  [CodeCov]

The whiteprint command line is under [GPL-3.0-or-later] license, however the
code templates used to generate the code are under [MIT-0] license.


### Try it!

All you need is a working `uv`. If you don't already have it just open a
terminal and run:

```console
# On macOS and Linux.
$ curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows.
$ powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# With pip.
$ pip install uv
```

Then just run whiteprints with uvx:

```
$ uvx whiteprints init my_awesome_project
```
Answer a few questions and you're ready to go 🚀.

This will create a directory named `my_awesome_project` containing your [Python] project.

To generate a [GitHub] template please look at the command line help

```
$ uvx whiteprints init --help
```

You may also have a look at the [Documentation](https://whiteprints.readthedocs.io/en/stable/)

## Documentation

See: https://whiteprints.readthedocs.io/en/stable/.

## Install

See [INSTALL.md](INSTALL.md).

## Maintainers

See [MAINTAINERS.md](MAINTAINERS.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licensing

The _[Python]_ **code** of this project is distributed under license [GPL-3.0-or-later].

In case of doubt, please check the [SPDX] header of each individual source code file.

[Python]: https://www.python.org/
[SPDX]: https://spdx.dev/
[REUSE]: https://reuse.software/
[uv]: https://docs.astral.sh/uv/
[Tox]: https://tox.wiki/
[Pytest]: https://docs.pytest.org/en/stable/
[Sphinx]: https://www.sphinx-doc.org/en/master/index.html
[PyPI]: https://pypi.org/
[ReadTheDocs]: https://about.readthedocs.com/
[CodeCov]: https://about.codecov.io/
[GPL-3.0-or-later]: https://spdx.org/licenses/GPL-3.0-or-later
[MIT-0]: https://spdx.org/licenses/MIT-0
[GitHub]:https://github.com/
