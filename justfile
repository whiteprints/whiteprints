# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


# Uncomment this to use project local uv cache.
# export UV_CACHE_DIR := ".just/.cache/uv"
export UV_NO_PROGRESS := "true"
export PYTHONOPTIMIZE := "0"
export PYTHONDONTWRITEBYTECODE := "1"


# list all receipts
@default:
    just --list

# Uses Python to mimic `readlink -m` functionality in a cross-platform manner.
[private]
@canonicalize path="":
    uvx python -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve().as_posix())" "{{ path }}"

[private]
@working-directory:
    just canonicalize "{{ justfile_directory() }}/.just"

# Print the receipt root directory
[private]
@root-path receipt="" python="" resolution="" dist="":
    just canonicalize "$(just working-directory)/{{ receipt }}/{{ if dist == '' { '' } else { file_stem(dist) } }}/{{ resolution }}/{{ python }}"

# Print the receipt temporary directory
[private]
@tmp-path receipt="" python="" resolution="" dist="":
    just canonicalize "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/tmp"

# Print the receipt coverage directory
[private]
@coverage-path receipt="" python="" resolution="" dist="":
    just canonicalize "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/coverage"

# Print the receipt tests results directory
[private]
@tests-results-path receipt="" python="" resolution="" dist="":
    just canonicalize "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/tests-results"

# Print the virtualenv path to a receipt
[group("virtualenv")]
@venv-path receipt="" python="" resolution="" dist="":
    just canonicalize "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/.venv"

[private]
@venv-python receipt="" python="" resolution="" dist="":
    uv python find "$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")"

# initialise Just working directory and synchronize the virtualenv
[private]
@init:
    [ -d $(just working-directory) ] || mkdir -p $(just working-directory)

# run all tests
all:
    @just pre-commit
    @just lint
    @just check-vulnerabilities
    @just check-exceptions
    @just check-code-maintainability
    @just for-all-python check-types
    @just for-all-python test-repository
    @just coverage
    @just BOM
    @just check-documentation-links
    @just build-documentation
    @just build

# Create a virtual environment for a receipt, Python and optionally a dist
[private]
@venv receipt python resolution="" dist="": init
    [ -d "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")" ] || \
        mkdir -p "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")"
    rm -rf "$(just tmp-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")"
    mkdir -p "$(just tmp-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")"
    uv venv \
        --relocatable \
        --no-project \
        --no-config \
        --python={{ python }} \
        --prompt={{ receipt }} \
        "$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")"

# Run `uv`
[private]
uv args="":
    uv \
    {{ args }}

# Run `uv run`
[private]
uvr args="":
    @just uv " \
        run \
        --refresh \
        --isolated \
        --no-dev \
        --no-config \
        --no-editable \
        --frozen \
        --exact \
        {{ args }} \
    "

# Run `uv tool run`
[private]
uvx args="":
    @just uv " \
        tool run \
        --isolated \
        {{ args }} \
    "

# Export a pip requirements file
[private]
compile args="":
    @just uv " \
        pip compile \
        --quiet \
        --refresh \
        --generate-hashes \
        --all-extras \
        {{ args }} \
    "

# Install dev requirements (group)
[private]
requirements group args="":
    @just uv " \
        export \
        --no-config \
        --no-emit-project \
        --quiet \
        --frozen \
        --no-dev \
        {{ if group == '' { '' } else { '--group=' + group } }} \
        {{ args }} \
    "

# Install dev requirements (group)
[private]
requirements-dev args="":
    @just uv " \
        export \
        --no-config \
        --no-emit-project \
        --quiet \
        --frozen \
        --only-dev \
        {{ args }} \
    "

# Synchronize lockfile and environment
[group("manage project")]
sync resolution="highest":
    @just uv " \
        sync \
        --resolution={{ resolution }} \
        --all-extras \
    "

# Clean Python temporary files
[group("clean")]
clean-python:
    @just uvx "pyclean ."

# Clean the generated Bill of Material (BOM)
[group("clean")]
clean-BOM:
    rm -rf BOM

# Clean the documentation
[group("clean")]
clean-docs:
    rm -rf docs_build

# Clean the just working directory
[group("clean")]
clean-just:
    rm -rf $(just working-directory)

# Clean the compiled translation file
[group("clean")]
clean-translation:
    find src/ -name *.mo -type f -delete

# Clean the source distribution and wheel directory
[group("clean")]
clean-distribution:
    rm -rf dist

[group("clean")]
clean-uv-cache:
    @just uv "cache prune"

[group("clean")]
clean-coverage:
    find $(just working-directory) -name "coverage" -type d -exec rm -r {} +

# Clean everything
[group("clean")]
clean-all:
    @just clean-coverage
    @just clean-python
    @just clean-BOM
    @just clean-just
    @just clean-docs
    @just clean-translation
    @just clean-distribution

# Run a receipt for all Python versions (found in the .python-versions file). Works for all receipt whose first argument is a Python version
[group("tests")]
for-all-python receipt args="":
    for python in $(grep -v '^#' .python-versions); do \
        just {{ receipt }} $python {{ args }}; \
    done

alias ap := for-all-python

# pip freeze
[private]
freeze receipt python resolution="" dist="":
    @just uv " \
        pip freeze \
            --system \
            --python="$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")" \
        | tee "$(just root-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/requirements-dev.txt" \
    "

# pip install in a virtualenv
[group("virtualenv")]
install receipt python group link_mode="":
    @just requirements {{ group }} " \
        --output-file="$(just tmp-path {{ receipt }} {{ python }})/requirements.txt" \
        --python="$(just venv-path {{ receipt }} {{ python }})" \
    "
    @just uv " \
        pip install  \
            --quiet \
            --exact \
            --strict \
            --require-hashes \
            {{ if link_mode == '' { '' } else { '--link-mode=' + link_mode } }} \
            --requirements="$(just tmp-path {{ receipt }} {{ python }})/requirements.txt" \
            --prefix="$(just venv-path {{ receipt }} {{ python }})" \
            --python="$(just venv-path {{ receipt }} {{ python }})" \
    "
    @just freeze "{{ receipt }}" "{{ python }}"

# pip install in a virtualenv
[group("virtualenv")]
install-distribution receipt python dist resolution="highest" link_mode="" group="":
    @[ -z "{{ group }}" ] && \
        touch "$(just tmp-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/requirements-dev.txt" || \
        just requirements-dev " \
            {{ if group == '' { '' } else { '--only-group=' + group } }} \
            --output-file=\"$(just tmp-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/requirements-dev.txt\" \
            --python=\"$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\" \
        "
    @just uv " \
        pip install {{ dist }} \
            --quiet \
            --exact \
            --strict \
            --resolution={{ resolution }} \
            {{ if link_mode == '' { '' } else { '--link-mode=' + link_mode } }} \
            --requirements=\"$(just tmp-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/requirements-dev.txt\" \
            --prefix=\"$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\" \
            --python=\"$(just venv-path \"{{ receipt }}\" \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\" \
    "
    @just freeze "{{ receipt }}" "{{ python }}" "{{ resolution }}" "{{ dist }}"

# Run pytest from a given python interpreter
[private]
pytest-from-venv python-path tmp-path coverage-path tests-results-path:
    TMPDIR="{{ tmp-path }}" \
    COVERAGE_FILE="${{ coverage-path }}/coverage.{{ arch() }}-{{ os() }}" \
    {{ python-path }} -m pytest \
        --html="{{ tests-results-path }}/test_report.{{ arch() }}.{{ os() }}.html" \
        --junitxml="{{ tests-results-path }}/.junit-{{ arch() }}-{{ os() }}.xml" \
        --md-report-output="{{ tests-results-path }}/test_report_{{ arch() }}_{{ os() }}.md" \
        --basetemp="{{ tmp-path }}" \
        --cov-config=".coveragerc" \
        'src' \
        'tests'

# Run the tests with pytest for a given Python and distribution for a given resolution.
[group("tests")]
test-distribution python dist resolution="highest" link_mode="": (venv "test-distribution" python resolution dist)
    @just install-distribution test-distribution {{ python }} {{ dist }} {{ resolution }} "{{ link_mode }}" tests
    @just pytest-from-venv \
        "$(just venv-path test-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/bin/python" \
        "$(just tmp-path test-distribution \"{{ python }}\" \"{{ resolution}}\" \"{{ dist }}\")" \
        "$(just coverage-path test-distribution \"{{ python }}\" \"{{ resolution}}\" \"{{ dist }}\")" \
        "$(just tests-results-path test-distribution \"{{ python }}\" \"{{ resolution}}\" \"{{ dist }}\")"

alias test-dist := test-distribution
alias td := test-distribution

# Run the tests with pytest for lowest and highest resolutions
[group("tests")]
test-distribution-low-high python dist link_mode="":
    @just test-distribution {{ python }} {{ dist }} lowest "{{ link_mode }}"
    @just test-distribution {{ python }} {{ dist }} highest "{{ link_mode }}"


alias test-dist-lh := test-distribution-low-high
alias tdlh := test-distribution-low-high

# Run the tests with pytest for a given Python
[group("tests")]
test-repository python: (venv "test-repository" python)
    @TMPDIR="$(just tmp-path test-repository {{ python }})" \
    COVERAGE_FILE="$(just coverage-path test-repository {{ python }})/coverage.{{ arch() }}-{{ os() }}" \
    just uvr " \
        --group=tests \
        --python=\"$(just venv-path test-repository {{ python }})\" \
    pytest \
        --html=\"$(just tests-results-path test-repository {{ python }})/test_report.{{ arch() }}.{{ os() }}.html\" \
        --junitxml=\"$(just tests-results-path test-repository {{ python }})/.junit-{{ arch() }}-{{ os() }}.xml\" \
        --md-report-output=\"$(just tests-results-path test-repository {{ python }})/test_report_{{ arch() }}_{{ os() }}.md\" \
        --basetemp=\"$(just tmp-path test-repository {{ python }})\" \
        --cov-config=".coveragerc" \
        'src' \
        'tests' \
    "
    @just uvx "pyclean ."

alias test-repo := test-repository
alias tr := test-repository

# Run the tests with pytest
[group("tests")]
@test python dist="" resolution="highest" link_mode="":
    [ -z "{{ dist }}" ] && (just test-repository "{{ python }}") || (just test-distribution "{{ python }}" "{{ dist }}" "{{ resolution }}" "{{ link_mode }}")

[private]
open-in-browser path:
    $BROWSER {{ path }}

# Open a test report in a web browser
[group("report")]
open-test-report python dist="" resolution="highest":
    @[ -z "{{ dist }}" ] \
        && ([ -f "$(just tests-results-path test-repository {{ python }})/test_report.{{ arch() }}.{{ os() }}.html" ] || just test-repository {{ python }}) \
        || ([ -f "$(just tests-results-path test-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/test_report.{{ arch() }}.{{ os() }}.html" ] || just test-distribution {{ python }} {{ dist }} {{ resolution }})
    @[ -z "{{ dist }}" ] \
        && ([ -f "$(just tests-results-path test-repository {{ python }})/test_report.{{ arch() }}.{{ os() }}.html" ] && just open-in-browser "$(just tests-results-path test-repository {{ python }})/test_report.{{ arch() }}.{{ os() }}.html") \
        || ([ -f "$(just tests-results-path test-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/test_report.{{ arch() }}.{{ os() }}.html" ] && just open-in-browser "$(just tests-results-path test-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/test_report.{{ arch() }}.{{ os() }}.html")

# Open repository test reports for all pythons
[group("report")]
open-all-tests-reports dist="":
    @[ -z "{{ dist }}" ] \
        && (just open-in-browser "$(find $(just root-path test-repository) -name 'test_report.*.*.html' -printf '\\"%p\\"\n' | xargs echo)") \
        || (just open-in-browser "$(find $(just root-path test-distribution \"\" \"\" \"{{ dist }}\") -name 'test_report.*.*.html' -printf '\\"%p\\"\n' | xargs echo)")

[group("report")]
open-coverage-report:
    @[ -f "$(just coverage-path test-repository)/htmlcov/index.html" ] || just coverage-report
    @just open-in-browser "$(just coverage-path test-repository)/htmlcov/index.html"

# Run pre-commit
[private]
pre-commit args="":
    @just uvx " \
        --with pre-commit-uv \
    pre-commit run \
        --all-files \
        --show-diff-on-failure \
        {{ args }} \
    "

# Lint the project with pylint
[group("repository analysis")]
lint:
    @just uvr " \
        --group=lint \
    pylint \
        --rcfile '.pylintrc' \
        'src' \
        'tests' \
        'docs' \
    "

# Run `pyright`
[private]
pyright args="":
    @just uvx " \
        pyright \
        {{ args }} \
    "

# Check the types correctness with Pyright for a given Python
[group("tests")]
check-types-distribution python dist resolution="highest" link_mode="": (venv "check-types-distribution" python resolution dist)
    @just install-distribution check-types-distribution "{{ python }}" "{{ dist }}" "{{ resolution }}" "{{ link_mode }}"
    @cp 'pyrightconfig.json' "\"$(just root-path check-types-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\""
    @just pyright " \
        --project=\"$(just root-path check-types-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")/pyrightconfig.json\" \
        --pythonpath=\"$(uv python-path check-types-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\" \
        $(uv run \
            --no-project \
            --python=\"$(just venv-path check-types-distribution \"{{ python }}\" \"{{ resolution }}\" \"{{ dist }}\")\" \
            python -c \"import sys,re,os,importlib.metadata as m; w=sys.argv[1]; m_obj=re.match(r'(.+?)-\\d', os.path.basename(w)); assert m_obj, 'Regex did not match input: ' + os.path.basename(w); d=m_obj.group(1); dist=m.distribution(d); t=(dist.read_text('top_level.txt') or d).splitlines()[0]; print(os.path.abspath(os.path.join(dist.locate_file(''), t)))\" {{ dist }} \
        ) \
    "

alias check-types-dist := check-types-distribution
alias ctd := check-types-distribution

# Run the type correctness with Pyright for a given Python for both lowest and highest resolutions
[group("tests")]
check-types-distribution-lh python dist link_mode="":
    @just check-types-distribution {{ python }} {{ dist }} lowest "{{ link_mode }}"
    @just check-types-distribution {{ python }} {{ dist }} highest "{{ link_mode }}"

alias check-types-dist-lh := check-types-distribution-lh
alias ctdlh := check-types-distribution-lh

# Check the types corectness with Pyright for a given Python
[group("tests")]
check-types-repository python link_mode="": (venv "check-types-repository" python)
    @just install check-types-repository {{ python }} tests "{{ link_mode }}"
    @just pyright " \
        --pythonpath=\"$(uv python-path check-types-distribution \"{{ python }}\")\" \
        --project='pyrightconfig.json' \
        src/ tests/ docs/ \
    "

alias check-types := check-types-repository

# Print the dependency tree for a given Python
[group("dependencies")]
print-dependency-tree python: (venv "print-dependency-tree" python)
    uv tree \
        --python="$(just venv-path check-types-repository {{ python }})" \
        --frozen \
        --no-dev

# Print the outdated dependencies for a given Python
[group("dependencies")]
print-outdated-direct-dependencies python: (venv "print-outdated-direct-dependencies" python)
    uv tree \
        --python="$(just venv-path print-outdated-direct-dependencies {{ python }})" \
        --frozen \
        --outdated \
        --depth 1

# Build the project source distribution and wheel
[group("manage project")]
build:
    @just uv build


# Check the given wheel
[group("tests")]
check-wheel wheel="dist/":
    @[ ! -e {{ wheel }} ] || just uvx "check-wheel-contents {{ wheel }} --src-dir=src/ --package-omit=\*.pyc,\*.pot,\*.po"


# Combine coverage files
[group("coverage")]
coverage-combine:
    @[ "$(find $(just root-path test-repository) -type f -name 'coverage.*-*')" ] \
        || just for-all-python test-repository
    just uvr " \
        --only-group=coverage \
    coverage combine \
        --rcfile='.coveragerc' \
        --data-file=$(just coverage-path test-repository)/coverage-combined \
        $(find $(just root-path test-repository) -type f -name 'coverage.*-*' | xargs echo) \
    "

# Report coverage in various formats (lcov, html, xml)
[group("report")]
coverage-report:
    @[ -d "$(just coverage-path test-repository)" ] || \
        just coverage-combine
    just uvr " \
        --only-group=coverage \
    coverage html \
        --rcfile='.coveragerc' \
        --directory=$(just coverage-path test-repository)/htmlcov \
        --data-file=$(just coverage-path test-repository)/coverage-combined \
    "
    @COVERAGE_FILE="$(just coverage-path test-repository)/coverage-combine" \
    just uvr " \
        --only-group=coverage \
    coverage lcov \
        --rcfile='.coveragerc' \
        -o$(just coverage-path test-repository)/coverage.lcov \
        --data-file=$(just coverage-path test-repository)/coverage-combined \
    "
    @COVERAGE_FILE="$(just coverage-path test-repository)/coverage-combine" \
    just uvr " \
        --only-group=coverage \
    coverage xml \
        --rcfile='.coveragerc' \
        -o$(just coverage-path test-repository)/coverage.xml \
        --data-file=$(just coverage-path test-repository)/coverage-combined \
    "

# Print coverage
[group("coverage")]
coverage args="":
    @[ -d "$(just coverage-path test-repository)" ] || \
        just coverage-combine
    just uvr " \
        --only-group=coverage \
    coverage report \
        --rcfile='.coveragerc' \
        --data-file=$(just coverage-path test-repository)/coverage-combined \
        --skip-covered \
        {{ args }} \
    "

# Run `reuse`
[private]
reuse args="":
    @just uvx " \
        reuse \
        {{ args }} \
    "

# Export Bill of Material of project's files and their licenses
[group("Bill of Material")]
BOM-licenses:
    [ -d "BOM" ] || mkdir "BOM"
    @just reuse " \
        spdx \
        --creator-organization 'whiteprints <whiteprints@pm.me>' \
        --output BOM/project_licenses.spdx \
    "

# Run `pip-audit`
[private]
pip-audit args="":
    @just uvx " \
        pip-audit \
        --disable-pip \
        --require-hashes \
        {{ args }} \
    "

# Export Bill of Material of project's dependencies and vulnerabilities for a given Python
[group("Bill of Material")]
BOM-vulnerabilities python resolution="lowest": (venv "BOM-vulnerabilities" python resolution)
    [ -d "BOM" ] || \
        mkdir -p "BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}"
    @just compile " \
        --python=$(just venv-path BOM-vulnerabilities {{ python }} {{ resolution }}) \
        --resolution={{ resolution }} \
        --output-file '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution }}/\
            requirements.txt\
        ' \
        pyproject.toml \
    "
    @just uvx " \
        --from cyclonedx-bom \
    cyclonedx-py requirements \
        --outfile \
            '\
                BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution }}/\
                project_dependencies.cdx.json\
            ' \
        '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution}}/\
            requirements.txt\
        ' \
    "
    @just pip-audit " \
        --requirement '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution }}/\
            requirements.txt\
        ' \
        --format cyclonedx-json \
        --output '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution }}/\
            vulnerabilities.cdx.json\
        ' \
    "

# Export a Bill of Material of project files licenses and dependencies
[group("Bill of Material")]
BOM:
    @just BOM-licenses
    @just for-all-python BOM-vulnerabilities

# Try to autofix a maximum of errors and typos
[group("manage project")]
autofix:
    -@just pre-commit trailing-whitespace
    -@just pre-commit pyproject-fmt
    -@just pre-commit ruff-format
    -@just pre-commit ruff

# Run `bandit`
[private]
bandit args="":
    @just uvx " \
        bandit \
        {{ args }} \
    "

# Check code vulnerabilities (repository analysis)
[group("repository analysis")]
check-vulnerabilities:
    @just bandit " \
        --recursive \
        --configfile=bandit.yaml \
        src \
        tests \
        docs \
    "

# Run `tryceratops`
[private]
tryceratops args="":
    @just uvr " \
        --group=check-exceptions \
        tryceratops \
        {{ args }} \
    "

# Check code exceptions (repository analysis)
[group("repository analysis")]
check-exceptions:
    @just tryceratops " \
        src \
        tests \
        docs \
    "

# Run `radon`
[private]
radon args="":
    @just uvx " \
        radon \
        {{ args }} \
    "

# Print a report of the project's code complexity
[group("repository analysis")]
audit-code-maintainability:
    @just radon " \
        mi \
        tests \
        docs \
        src \
    "

# Run `xenon`
[private]
xenon args="":
    @just uvx " \
        xenon \
        {{ args }} \
    "

# Check code complexity
[group("repository analysis")]
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
[group("repository analysis")]
check-licenses:
    @just reuse lint

# Check for vulnerabilities in the dependencies
[group("repository analysis")]
check-supply-chain python resolution="lowest": (venv ("check-supply-chain-" + resolution) python)
    @just compile " \
        --python='\
            $(just venv-path check-supply-chain {{ python }} {{ resolution }}) \
        ' \
        --resolution={{ resolution }} \
        --output-file '\
            $(just root-path check-supply-chain {{ python }} {{ resolution }})/requirements.txt \
        ' \
        pyproject.toml \
    "
    @just pip-audit " \
        --requirement '\
            $(just root-path check-supply-chain {{ python }} {{ resolution }})/requirements.txt \
        ' \
    "

# Run `sphinx-build`
[private]
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
[group("documentation")]
build-documentation dest="docs_build":
    @just sphinx-build "--builder=html '{{ dest }}'"

# Check that there are no dead links in the documentation
[group("documentation")]
check-documentation-links dest="docs_build":
    @just sphinx-build "--builder=linkcheck '{{ dest }}'"

# Run `sphinx-autobuild`
[private]
sphinx-autobuild args="":
    @just uvr " \
            --group=serve-documentation \
        sphinx-autobuild \
            --jobs=auto \
            --keep-going \
            --open-browser \
        docs \
        $(just tmp-path sphinx-autobuild)/docs_build \
        {{ args }} \
    "

# Serve the documentation on a given port. If port=0 a random available port is set.
[group("documentation")]
serve-documentation port="0":
    @just sphinx-autobuild "--port={{ port }}"

# Run `pybabel`
[private]
pybabel args="":
    @just uvr " \
        --only-group=localization \
    pybabel \
        --quiet \
        {{ args }} \
    "

# Extract the translation from the Python source files
[group("localization")]
translation-extract:
    @just pybabel " \
        extract \
            --omit-header \
            --sort-by-file \
            --output 'src/whiteprints/locale/base.pot' \
            src \
    "

# Initialize a translation for a given locale (language)
[group("localization")]
translation-init locale:
    @just pybabel " \
        init \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

# Update a translation for a given locale (language)
[group("localization")]
translation-update locale="":
    @just pybabel " \
        update \
            --omit-header \
            --input-file 'src/whiteprints/locale/base.pot' \
            --output-dir 'src/whiteprints/locale' \
            --locale='{{ locale }}' \
    "

# Install or update the tools used by Just receipts
[group("manage project")]
dev-tools-upgrade:
    @just uv "tool install --upgrade rust-just"
    @just uv "tool install --upgrade pre-commit --with=pre-commit-uv"
    @just uv "tool install --upgrade reuse"
    @just uv "tool install --upgrade pip-audit"
    @just uv "tool install --upgrade ruff"
    @just uv "tool install --upgrade cyclonedx-bom"
    @just uv "tool install --upgrade pyright"
