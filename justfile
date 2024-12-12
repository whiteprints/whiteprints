# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


default:
    @just --list

init:
    [ -d .just ] || mkdir .just

all:
    @just pre-commit
    @just lint
    @just check-vulnerabilities
    @just for-all-python check-types
    @just for-all-python test
    @just coverage
    @just BOM

venv session python: init
    [ -d ".just/{{ session }}/{{ python }}" ] || \
       mkdir -p ".just/{{ session }}/{{ python }}"
    [ -d ".just/{{ session }}/{{ python }}/tmp" ] || \
       mkdir -p ".just/{{ session }}/{{ python }}/tmp"
    [ -d ".just/{{ session }}/{{ python }}/.venv" ] || \
        uv venv \
            --no-project \
            --no-config \
            --python={{ python }} \
            ".just/{{ session }}/{{ python }}/.venv"

uv args="":
    uv \
    {{ args }}

uvr args="":
    @just uv " \
        run \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        {{ args }} \
    "

uvx args="":
    @just uv " \
        tool run \
        --isolated \
        {{ args }} \
    "

clean-python:
    @just uvx "pyclean ."

clean-BOM:
    rm -rf BOM

clean-docs:
    rm -rf docs_build

clean-just:
    rm -rf .just

clean-translation:
    find src/ -name *.mo -type f -delete

clean-all:
    @just clean-python
    @just clean-BOM
    @just clean-just
    @just clean-docs
    @just clean-translation

for-all-python session:
    for python in `grep -v '^#' {{ justfile_directory() }}/.python-versions`; do \
        just {{ session }} $python; \
    done

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
            /.just/test/{{ python }}/.venv/bin/python\
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
        '\
        --basetemp="{{ justfile_directory() }}/.just/test/{{ python }}/tmp" \
        --cov-config="{{ justfile_directory() }}/.coveragerc" \
        "{{ justfile_directory() }}/src" \
        "{{ justfile_directory() }}/tests" \
    "

test-report python:
    $BROWSER "{{ justfile_directory() }}/.just/.test_report.{{ python }}.html"

pre-commit args="":
    @just uvx " \
        --with pre-commit-uv \
    pre-commit run \
        --all-files \
        --show-diff-on-failure \
        {{ args }} \
    "

lint:
    @just uvr " \
        --group=lint \
    pylint \
        --rcfile '{{ justfile_directory() }}/.pylintrc' \
        '{{ justfile_directory() }}/src' \
        '{{ justfile_directory() }}/tests' \
        '{{ justfile_directory() }}/docs' \
    "

check-types python: (venv "check-types" python)
    @just uvr " \
        --python='\
            {{ justfile_directory() }}/\
            .just/check-types/{{ python }}/.venv/bin/python\
        ' \
        --group=check-types \
    pyright \
        --pythonpath='\
            {{ justfile_directory() }}/\
            .just/check-types/{{ python }}/.venv/bin/python\
        ' \
        --project="{{ justfile_directory() }}/pyrightconfig.json" \
    "

print-dependency-tree python: (venv "print-dependency-tree" python)
    uv tree \
        --python="\
            {{ justfile_directory() }}/\
            .just/print-dependency-tree/{{ python }}/.venv/bin/python\
        " \
        --frozen \
        --no-dev

build:
    uv build

coverage-combine:
    @[ "$(find .just -maxdepth 1 -type f -name '.coverage.*')" ] \
        || just all test
    @just uvr " \
        --directory='.just' \
        --only-group=coverage \
    coverage combine \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        --data-file=.coverage \
    "

coverage:
    @[ -f "{{ justfile_directory() }}/.just/.coverage" ] || \
        just coverage-combine
    @just uvr " \
        --only-group=coverage \
    coverage report \
        --rcfile='{{ justfile_directory() }}/.coveragerc' \
        --data-file='{{ justfile_directory() }}/.just/.coverage' \
        --skip-covered \
    "

reuse args="":
    @just uvx " \
        reuse \
        {{ args }} \
    "

BOM-licenses:
    [ -d "BOM" ] || mkdir "BOM"
    @just reuse " \
        spdx \
        --creator-organization 'whiteprints <whiteprints@pm.me>' \
        --output BOM/project_licenses.spdx \
    "

pip-audit args="":
    @just uvx " \
        pip-audit \
        --disable-pip \
        --require-hashes \
        {{ args }} \
    "

requirements args="":
    @just uv " \
        export \
        --quiet \
        --frozen \
        --no-dev \
        --no-emit-project \
        {{ args }} \
    "

BOM-vulnerabilities python:
    [ -d "BOM" ] || mkdir -p "BOM/vulnerabilities-{{ python }}"
    @just requirements " \
        --output-file 'BOM/vulnerabilities-{{ python }}/requirements.txt' \
    "
    @just uvx " \
        --from cyclonedx-bom \
    cyclonedx-py requirements \
        --outfile \
            'BOM/vulnerabilities-{{ python }}/project_dependencies.cdx.json' \
        'BOM/vulnerabilities-{{ python }}/requirements.txt' \
    "
    @just pip-audit " \
        --requirement 'BOM/vulnerabilities-{{ python }}/requirements.txt' \
        --format cyclonedx-json \
        --output 'BOM/vulnerabilities-{{ python }}/vulnerabilities.cdx.json' \
    "

BOM:
    @just BOM-licenses
    @just for-all-python BOM-vulnerabilities

autofix:
    -@just pre-commit trailing-whitespace
    -@just pre-commit pyproject-fmt
    -@just pre-commit ruff-format
    -@just pre-commit ruff

bandit args="":
    @just uvx " \
        bandit \
        {{ args }} \
    "

check-vulnerabilities:
    @just bandit " \
        --recursive \
        --configfile=bandit.yaml \
        {{ justfile_directory() }}/src \
        {{ justfile_directory() }}/tests \
        {{ justfile_directory() }}/docs \
    "

radon args="":
    @just uvx " \
        radon \
        {{ args }} \
    "

audit-code-maintainability:
    @just radon " \
        mi \
        tests \
        docs \
        src \
    "

xenon args="":
    @just uvx " \
        xenon \
        {{ args }} \
    "

check-code-maintainability:
    @just xenon " \
        --max-average=A \
        --max-modules=A \
        --max-absolute=A \
        tests \
        docs \
        src \
    "

check-licenses:
    @just reuse lint

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

sphinx-build args="":
    @just uvr " \
            --group=build-documentation \
        sphinx-build \
            --jobs=auto \
            --fail-on-warning \
            --keep-going \
        docs \
        docs_build \
        {{ args }} \
    "

build-documentation:
    @just sphinx-build --builder=html

check-documentation-links:
    @just sphinx-build --builder=linkcheck

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

serve-documentation port="0":
    @just sphinx-autobuild "--port={{ port }}"

pybabel args="":
    @just uvr " \
        --only-group=localization \
    pybabel \
        --quiet \
        {{ args }} \
    "

translation-extract:
    @just pybabel " \
        extract \
            --omit-header \
            --sort-by-file \
            --output 'src/whiteprints/locale/base.pot' \
            src \
    "

translation-init locale:
    @just pybabel " \
        init \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

translation-update locale="":
    @just pybabel " \
        update \
            --omit-header \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

install-dev-tools:
    @just uv "tool install --upgrade pip-audit"
    @just uv "tool install --with pre-commit-uv --upgrade pre-commit"
    @just uv "tool install pyright"
    @just uv "tool install reuse"
    @just uv "tool install ruff"
    @just uv "tool install cyclonedx-bom"
