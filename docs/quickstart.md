<!--
SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# ⚡ Quickstart

All you need is a working `uv`. If you don't already have it just open a
terminal and run:

- On macOS and Linux:
  ```console
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- On Windows:
  ```console
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- With pip:
  ```console
  pip install uv
  ```

Then just run whiteprints with uvx:

```
uvx whiteprints init my_awesome_project
```
Answer a few questions and you're ready to go 🚀.

This will create a directory named `my_awesome_project` containing your [Python] project.

To generate a [GitHub] template please look at the command line help

```
uvx whiteprints init --help
```

If you plan to use whiteprints frequently you can have a look at the
[installation guide](INSTALL.md).

[GitHub]: https://github.com
[Python]: https://www.python.org/
[uv]: https://docs.astral.sh/uv/
