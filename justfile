# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


default:
    @just --list

init:
    [ -d .just ] || mkdir .just

clean:
    rm -rf .just

venv session python: init
    [ -d ".just/{{ session }}/{{ python }}" ] || \
        mkdir -p ".just/{{ session }}/{{ python }}"
    [ -d ".just/{{ session }}/{{ python }}/tmp" ] || \
        mkdir -p ".just/{{ session }}/{{ python }}/tmp"
    [ -d ".just/{{ session }}/{{ python }}/.venv" ] || \
        uv venv --no-project --no-config --python={{ python }} ".just/{{ session }}/{{ python }}/.venv"

all session:
    for python in `cat {{ justfile_directory() }}/.python-versions`; do \
        just {{ session }} $python; \
    done

test python: (venv "test" python)
    TMPDIR="{{ justfile_directory() }}/.just/test/{{ python }}/tmp/" \
    PYTHONOPTIMIZE=0 \
    COVERAGE_FILE="{{ justfile_directory() }}/.just/.coverage.{{ arch() }}-{{ os() }}-{{ python }}" \
    uv run \
        --python="{{ justfile_directory() }}/.just/test/{{ python }}/.venv/bin/python" \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        --group=tests \
    pytest \
        --html="{{ justfile_directory() }}/.just/.test_report.{{ python }}.html" \
        --junitxml={{ justfile_directory() }}/.just/.junit.{{ python }}.xml \
        --md-report-output {{ justfile_directory() }}/.just/.test_report{{ python }}.md \
        --basetemp="{{ justfile_directory() }}/.just/test/{{ python }}/tmp" \
        --cov-config="{{ justfile_directory() }}/.coveragerc" \
        "{{ justfile_directory() }}/src" \
        "{{ justfile_directory() }}/tests"

test-report python:
    $BROWSER "{{ justfile_directory() }}/.just/.test_report.{{ python }}.html"

pre-commit:
    uvx \
        --isolated \
        --with pre-commit-uv \
    pre-commit run \
        --all-files --hook-stage=manual --show-diff-on-failure

lint:
    uv run \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        --group=lint \
    pylint \
        --rcfile "{{ justfile_directory() }}/.pylintrc" \
        "{{ justfile_directory() }}/src" \
        "{{ justfile_directory() }}/tests" \
        "{{ justfile_directory() }}/docs"

check-types python: (venv "check-types" python)
    uv run \
        --python="{{ justfile_directory() }}/.just/check-types/{{ python }}/.venv/bin/python" \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        --group=check-types \
    pyright \
        --pythonpath="{{ justfile_directory() }}/.just/check-types/{{ python }}/.venv/bin/python" \
        --project="{{ justfile_directory() }}/pyrightconfig.json"

print-dependency-tree python: (venv "print-dependency-tree" python)
    uv tree \
        --python="{{ justfile_directory() }}/.just/print-dependency-tree/{{ python }}/.venv/bin/python" \
        --frozen \
        --no-dev

build:
    uv build

coverage-combine:
    if [ find .just -maxdepth 1 -type f -name ".coverage.*" | grep -q . ]
    cd .just && \
    rm --force .coverage && \
    uv run \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        --only-group=coverage \
    coverage combine \
        --rcfile="{{ justfile_directory() }}/.coveragerc" \
        --data-file=.coverage \
        --keep

coverage:
    ([ -f "{{ justfile_directory() }}/.just/.coverage" ] || just coverage-combine ) && \
    uv run \
        --isolated \
        --no-dev \
        --no-editable \
        --frozen \
        --only-group=coverage \
    coverage report \
        --rcfile="{{ justfile_directory() }}/.coveragerc" \
        --data-file="{{ justfile_directory() }}/.just/.coverage" \
        --skip-covered
