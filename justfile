# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


# Uncomment this to use project local uv cache.
# export UV_CACHE_DIR := ".just/.cache/uv"
export UV_NO_PROGRESS := "true"


# list all receipts
default:
    @just --list

# initialise Just working directory and synchronize the virtualenv
init:
    [ -d .just ] || mkdir -p .just
    uv sync \
        --frozen \
        --all-groups \
        --all-extras

# run all tests
all:
    @just pre-commit
    @just lint
    @just check-vulnerabilities
    @just check-exceptions
    @just check-code-maintainability
    @just for-all-python check-types
    @just for-all-python test
    @just coverage
    @just BOM
    @just check-documentation-links
    @just build-documentation
    @just build

# Create a virtual environment for a receipt, Python and optionally a wheel
venv receipt python wheel="": init
    [ -d ".just/{{ receipt }}/{{ wheel }}/{{ python }}" ] || \
        mkdir -p ".just/{{ receipt }}/{{ wheel }}/{{ python }}"
    rm -rf ".just/{{ receipt }}/{{ wheel }}/{{ python }}/tmp"
    mkdir -p ".just/{{ receipt }}/{{ wheel }}/{{ python }}/tmp"
    uv venv \
        --no-project \
        --no-config \
        --python={{ python }} \
        ".just/{{ receipt }}/{{ wheel }}/{{ python }}/.venv"

# Run `uv`
uv args="":
    uv \
    {{ args }}

# Run `uv run`
uvr args="":
    @just uv " \
        run \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        {{ args }} \
    "

# Run `uv tool run`
uvx args="":
    @just uv " \
        tool run \
        --isolated \
        {{ args }} \
    "

# Export a pip requirements file
requirements args="":
    @just uv " \
        export \
        --quiet \
        --frozen \
        --no-dev \
        --no-emit-project \
        {{ args }} \
    "

# Clean Python temporary files
clean-python:
    @just uvx "pyclean ."

# Clean the generated Bill of Material (BOM)
clean-BOM:
    rm -rf BOM

# Clean the documentation
clean-docs:
    rm -rf docs_build

# Clean the just working directory
clean-just:
    rm -rf .just

# Clean the compiled translation file
clean-translation:
    find src/ -name *.mo -type f -delete

# Clean the sdist and wheel directory
clean-dist:
    rm -rf dist

clean-uv-cache:
    uv cache prune

# Clean everything
clean-all:
    @just clean-python
    @just clean-BOM
    @just clean-just
    @just clean-docs
    @just clean-translation
    @just clean-dist

# Run a receipt for all Python versions (found in the .python-versions file). Works for all receipt whose first argument is a Python version
for-all-python receipt args="":
    for python in `grep -v '^#' {{ justfile_directory() }}/.python-versions`; do \
        just {{ receipt }} $python {{ args }}; \
    done

# Run the tests with pytest for a given Python and wheel
test-wheel python wheel: (venv "test" python wheel)
    @just requirements " \
        --only-group=tests \
        --output-file='\
            {{ justfile_directory() }}\
            /.just/test/{{ wheel }}/{{ python }}/requirements-tests.txt\
        ' \
    "
    @TMPDIR="\
        {{ justfile_directory() }}/.just/test/{{ wheel }}/{{ python }}/tmp\
    " \
    PYTHONOPTIMIZE=0 \
    COVERAGE_FILE="\
        {{ justfile_directory() }}/\
        .just/.coverage.{{ arch() }}-{{ os() }}-{{ python }}\
    " \
    just uvr " \
        --with-requirements='\
            {{ justfile_directory() }}\
            /.just/test/{{ wheel }}/{{ python }}/requirements-tests.txt\
        ' \
        --with='{{ wheel }}' \
        --python='\
            {{ justfile_directory() }}\
            /.just/test/{{ wheel }}/{{ python }}/.venv\
        ' \
        --no-sync \
    pytest \
        --html='\
            {{ justfile_directory() }}/\
            .just/.test_report.{{ python }}.html\
        ' \
        --junitxml='\
            {{ justfile_directory() }}\
            /.just/.junit-{{ arch() }}-{{ os() }}-{{ python }}.xml\
        ' \
        --md-report-output='\
            {{ justfile_directory() }}/.just/.test_report{{ python }}.md\
        ' \
        --basetemp='\
            {{ justfile_directory() }}/\
            .just/test/{{ wheel }}/{{ python }}/tmp\
        ' \
        --cov-config='{{ justfile_directory() }}/.coveragerc' \
        '{{ justfile_directory() }}/src' \
        '{{ justfile_directory() }}/tests' \
    "

# Run the tests with pytest for a given Python
test python: (venv "test" python)
    @TMPDIR="{{ justfile_directory() }}/.just/test/{{ python }}/tmp/" \
    PYTHONOPTIMIZE=0 \
    COVERAGE_FILE="\
        {{ justfile_directory() }}/\
        .just/.coverage.{{ arch() }}-{{ os() }}-{{ python }}\
    " \
    just uvr " \
        --python='\
            {{ justfile_directory() }}\
            /.just/test/{{ python }}/.venv\
        ' \
        --group=tests \
    pytest \
        --html='\
            {{ justfile_directory() }}/\
            .just/.test_report.{{ python }}.html\
        ' \
        --junitxml='{{ justfile_directory() }}/.just/.junit.{{ python }}.xml' \
        --md-report-output='\
            {{ justfile_directory() }}/.just/.test_report{{ python }}.md\
        ' \
        --basetemp="{{ justfile_directory() }}/.just/test/{{ python }}/tmp" \
        --cov-config="{{ justfile_directory() }}/.coveragerc" \
        "{{ justfile_directory() }}/src" \
        "{{ justfile_directory() }}/tests" \
    "

# Open a test report in a web browser
test-report python:
    $BROWSER "{{ justfile_directory() }}/.just/.test_report.{{ python }}.html"

# Run pre-commit
pre-commit args="":
    @just uvx " \
        --with pre-commit-uv \
    pre-commit run \
        --all-files \
        --show-diff-on-failure \
        {{ args }} \
    "

# Lint the project with pylint
lint:
    @just uvr " \
        --group=lint \
    pylint \
        --rcfile '{{ justfile_directory() }}/.pylintrc' \
        '{{ justfile_directory() }}/src' \
        '{{ justfile_directory() }}/tests' \
        '{{ justfile_directory() }}/docs' \
    "

# Check the types corectness with Pyright for a given Python
check-types python: (venv "check-types" python)
    @just uvr " \
        --python='\
            {{ justfile_directory() }}/\
            .just/check-types/{{ python }}/.venv\
        ' \
        --group=check-types \
    pyright \
        --pythonpath='$( \
            uv python find \
            {{ justfile_directory() }}/.just/check-types/{{ python }}/.venv \
        )' \
        --project='{{ justfile_directory() }}/pyrightconfig.json' \
    "

# Print the dependency tree for a given Python
print-dependency-tree python: (venv "print-dependency-tree" python)
    uv tree \
        --python="\
            {{ justfile_directory() }}/\
            .just/print-dependency-tree/{{ python }}/.venv\
        " \
        --frozen \
        --no-dev

# Build the project sdist and wheel
build:
    uv build

# Combine coverage files
coverage-combine:
    @[ "$(find .just -maxdepth 1 -type f -name '.coverage.*')" ] \
        || just for-all-python test
    @just uvr " \
        --directory='.just' \
        --only-group=coverage \
    coverage combine \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        --data-file=.coverage \
    "

# Report coverage in various formats (lcov, html, xml)
coverage-report:
    @[ -f "{{ justfile_directory() }}/.just/.coverage" ] || \
        just coverage-combine
    @just uvr " \
        --only-group=coverage \
    coverage html \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        --directory='{{ justfile_directory() }}/.just/coverage/htmlcov' \
        --data-file='{{ justfile_directory() }}/.just/.coverage' \
    "
    @just uvr " \
        --only-group=coverage \
    coverage lcov \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        -o='{{ justfile_directory() }}/.just/coverage.lcov' \
        --data-file='{{ justfile_directory() }}/.just/.coverage' \
    "
    @just uvr " \
        --only-group=coverage \
    coverage xml \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        -o='{{ justfile_directory() }}/.just/coverage.xml' \
        --data-file='{{ justfile_directory() }}/.just/.coverage' \
    "

# Print coverage
coverage args="":
    @[ -f "{{ justfile_directory() }}/.just/.coverage" ] || \
        just coverage-combine
    @just uvr " \
        --only-group=coverage \
    coverage report \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        --data-file='{{ justfile_directory() }}/.just/.coverage' \
        --skip-covered \
        {{ args }} \
    "

# Run `reuse`
reuse args="":
    @just uvx " \
        reuse \
        {{ args }} \
    "

# Export Bill of Material of project's files and their licenses
BOM-licenses:
    [ -d "BOM" ] || mkdir "BOM"
    @just reuse " \
        spdx \
        --creator-organization 'whiteprints <whiteprints@pm.me>' \
        --output BOM/project_licenses.spdx \
    "

# Run `pip-audit`
pip-audit args="":
    @just uvx " \
        pip-audit \
        --disable-pip \
        --require-hashes \
        {{ args }} \
    "

# Export Bill of Material of project's dependencies and vulnerabilities for a given Python
BOM-vulnerabilities python:
    [ -d "BOM" ] || \
        mkdir -p "BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}"
    @just requirements " \
        --output-file '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
            requirements.txt\
        ' \
    "
    @just uvx " \
        --from cyclonedx-bom \
    cyclonedx-py requirements \
        --outfile \
            '\
                BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
                project_dependencies.cdx.json\
            ' \
        '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
            requirements.txt\
        ' \
    "
    @just pip-audit " \
        --requirement '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
            requirements.txt\
        ' \
        --format cyclonedx-json \
        --output '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
            vulnerabilities.cdx.json\
        ' \
    "

# Export a Bill of Material of project files licenses and dependencies
BOM:
    @just BOM-licenses
    @just for-all-python BOM-vulnerabilities

# Try to autofix a maximum of errors and typos
autofix:
    -@just pre-commit trailing-whitespace
    -@just pre-commit pyproject-fmt
    -@just pre-commit ruff-format
    -@just pre-commit ruff

# Run `bandit`
bandit args="":
    @just uvx " \
        bandit \
        {{ args }} \
    "

# Check code vulnerabilities (static analysis)
check-vulnerabilities:
    @just bandit " \
        --recursive \
        --configfile=bandit.yaml \
        {{ justfile_directory() }}/src \
        {{ justfile_directory() }}/tests \
        {{ justfile_directory() }}/docs \
    "

# Run `tryceratops`
tryceratops args="":
    @just uvr " \
        --group=check-exceptions \
        tryceratops \
        {{ args }} \
    "

# Check code exceptions (static analysis)
check-exceptions:
    @just tryceratops " \
        src \
        tests \
        docs \
    "

# Run `radon`
radon args="":
    @just uvx " \
        radon \
        {{ args }} \
    "

# Print a report of the project's code complexity
audit-code-maintainability:
    @just radon " \
        mi \
        tests \
        docs \
        src \
    "

# Run `xenon`
xenon args="":
    @just uvx " \
        xenon \
        {{ args }} \
    "

# Check code complexity
check-code-maintainability:
    @just xenon " \
        --max-average=A \
        --max-modules=A \
        --max-absolute=A \
        tests \
        docs \
        src \
    "

# Check licenses
check-licenses:
    @just reuse lint

# Check for vulnerabilities in the dependencies
check-supply-chain python: (venv "check-supply-chain" python)
    @just requirements " \
        --output-file '\
            {{ justfile_directory() }}/.just/check-supply-chain/\
            {{ python }}/tmp/requirements.txt\
        ' \
    "
    @just pip-audit " \
        --requirement '\
            {{ justfile_directory() }}/.just/check-supply-chain/\
            {{ python }}/tmp/requirements.txt\
        ' \
    "

# Run `sphinx-build`
sphinx-build args="":
    @just uvr " \
            --group=build-documentation \
        sphinx-build \
            --jobs=auto \
            --fail-on-warning \
            --keep-going \
        docs \
        {{ args }} \
    "

# Build the documentation
build-documentation dest="docs_build":
    @just sphinx-build "--builder=html '{{ dest }}'"

# Check that there are no dead links in the documentation
check-documentation-links dest="docs_build":
    @just sphinx-build "--builder=linkcheck '{{ dest }}'"

# Run `sphinx-autobuild`
sphinx-autobuild args="":
    @just uvr " \
            --group=serve-documentation \
        sphinx-autobuild \
            --jobs=auto \
            --keep-going \
            --open-browser \
        docs \
        '{{ justfile_directory() }}/.just/sphinx-autobuild/tmp/docs_build/' \
        {{ args }} \
    "

# Serve the documentation on a given port. If port=0 a random available port is set.
serve-documentation port="0":
    @just sphinx-autobuild "--port={{ port }}"

# Run `pybabel`
pybabel args="":
    @just uvr " \
        --only-group=localization \
    pybabel \
        --quiet \
        {{ args }} \
    "

# Extract the translation from the Python source files
translation-extract:
    @just pybabel " \
        extract \
            --omit-header \
            --sort-by-file \
            --output 'src/whiteprints/locale/base.pot' \
            src \
    "

# Initialize a translation for a given locale (language)
translation-init locale:
    @just pybabel " \
        init \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

# Update a translation for a given locale (language)
translation-update locale="":
    @just pybabel " \
        update \
            --omit-header \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

# Install or update the tools used by Just receipts
dev-tools-upgrade:
    @just uv "tool install --upgrade rust-just"
    @just uv "tool install --upgrade pre-commit --with=pre-commit-uv"
    @just uv "tool install --upgrade reuse"
    @just uv "tool install --upgrade pyright"
    @just uv "tool install --upgrade pip-audit"
    @just uv "tool install --upgrade ruff"
    @just uv "tool install --upgrade cyclonedx-bom"
