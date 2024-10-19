<!--
SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>

SPDX-License-Identifier: CC-BY-NC-SA-4.0
-->

# 📖 How-to guide

Thank you for your interest in improving this project.


The code is open-source under the license [CC-BY-NC-SA-4.0](../LICENSES/CC-BY-NC-SA-4.0.txt) and we
welcome contributions in any form.


As a contibutor, you must respect our [Code of Conduct].

[Code of Conduct]: CODE_OF_CONDUCT.md

## How to report a vulnerability

Refer to [SECURITY.md](SECURITY.md).

## How to report an identified bug

To report identified bugs, please fill a.[GitHub bug report issue](https://github.com/whiteprints/whiteprints/issues/new?template=bug_report.yml).

When filing a bug or issue, make sure to answer the following questions:

- Which operating system and Python version are you using?
- Which version of this project are you using?
- What actions did you take?
- What did you expect to see?
- What did you see instead?

Providing a test case and/or steps to reproduce the issue will help us address
your bug more effectively.


## How to request a feature

To request features, please [open a discussion](https://github.com/whiteprints/whiteprints/discussions/categories/ideas)

Once the enhancement has been discussed, fill a [GitHub feature issue](https://github.com/whiteprints/whiteprints/issues/new?template=feature_request.yml).

## How to report a problem

If you encounter any problems with the project, please contact any [core
members] via email.

[core member]: MAINTAINERS.md
[core members]: MAINTAINERS.md
[Maintainer]: MAINTAINERS.md
[Maintainers]: MAINTAINERS.md

## How to set up your development environment

You simply need [uv] and a copy of the repository.

[uv]: https://docs.astral.sh/uv/

To install python and setup your environment run

```console
uv python install
uv sync --all-extras
```

You can now run an interactive Python session:

```console
uv run python
```

If you whish to use a specific Python version you can use

```console
uv python pin ...
```

Please see [uv]'s documentation for more advanced usage.

## How to test the project

The test suite is managed by [Tox].

Run the full test suite:

```console
uvx tox run
```

List the available [Tox] sessions:

```console
uvx tox list
```

You can also run a specific [Tox] session.
For example, invoke the unit test suite like this:

```console
uvx tox run -m test
```

Unit tests are located in the _tests_ directory,
and are written using the [pytest] testing framework.

[pytest]: https://docs.pytest.org/en/stable/
[Tox]: https://tox.wiki/en/stable/

Please see [Tox]'s documentation for more advanced usage.

## How to submit changes

Create a new [Git] branch to submit changes to this project.

```console
git switch -c my-contribution
```

Then commit and push your modifications on your branch.

Your contribution needs to meet the following guidelines for acceptance:

  - The [Tox] test suite must pass without errors and warnings.
  - Include unit tests; this project maintains [100% code coverage](https://codecov.io/gh/whiteprints/whiteprints).
  - If your changes add functionality, update the documentation accordingly.

Feel free to submit early, though we can always iterate on this.

To run linting and code formatting checks before committing your changes, you
can install [pre-commit] as a [Git hook] by running:

```console
uvx pre-commit install
```

Please ensure that your contribution is resolving a known [issue]. If not,
please create an associated [issue] first.

Once your code and your issue are ready, create a [GitHub] [Pull Request]
containing your modification and referencing the associated [issue].

If you don't know or are not sure on how to create a Pull Request, follow
the tutorial [creating a Pull Request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request).

[GitHub]: https://github.com/
[Pull Request]: https://github.com/whiteprints/whiteprints/pulls
[issue]: https://github.com/whiteprints/whiteprints/issues

[Git hook]: https://git-scm.com/book/ms/v2/Customizing-Git-Git-Hooks
[Git]: https://git-scm.com/
[pre-commit]: https://pre-commit.com/

### Checklist

Before submitting changes:

- I agree to follow this project's [Code of Conduct](CODE_OF_CONDUCT.md)
- I have performed a self-review of my own code
- I have included relevant tests
- I have commented my code, particularly in hard-to-understand areas
- I have made corresponding changes to the documentation

### Contributor License Agreement

By making a contribution to this project, I (the contributor) hereby certify that

- The contributor represents and warrants, on behalf of their employer or other principal **if** they are acting within the scope of their employment or otherwise as the agent of a legal entity, that they have the right and authority to make their contribution under these terms.
- The contribution was created in whole or in part by me and I have the right to submit it under the license of the file(s) modified or created; **or**
- the contribution is based upon previous work that, to the best of my knowledge, is covered under an appropriate open source license and I have the right under that license to submit that work with modifications, whether created in whole or in part by me, under the license of the file(s) modified or created.
