# SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>
#
# SPDX-License-Identifier: GPL-3.0-or-later


# Uncomment this to use project local uv cache.
# export UV_CACHE_DIR := ".just/.cache/uv"
export UV_NO_PROGRESS := "true"
export PYTHONOPTIMIZE := "0"
export PYTHONDONTWRITEBYTECODE := "1"


# list all receipts
default:
    @just --list

# initialise Just working directory and synchronize the virtualenv
[private]
init:
    [ -d .just ] || mkdir -p .just

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
venv receipt python dist="": init
    [ -d ".just/{{ receipt }}{{ if dist == '' { '' } else { '/' + file_stem(dist) } }}/{{ python }}" ] || \
        mkdir -p ".just/{{ receipt }}{{ if dist == '' { '' } else { '/'+ file_stem(dist) } }}/{{ python }}"
    rm -rf ".just/{{ receipt }}{{ if dist == '' { '' } else { '/' + file_stem(dist) } }}/{{ python }}/tmp"
    mkdir -p ".just/{{ receipt }}{{ if dist == '' { '' } else { '/' + file_stem(dist) } }}/{{ python }}/tmp"
    uv venv \
        --no-project \
        --no-config \
        --python={{ python }} \
        ".just/{{ receipt }}{{ if dist == '' { '' } else { '/' + file_stem(dist) } }}/{{ python }}/.venv"

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
        --group={{ group }}\
        {{ args }} \
    "

# Install dev requirements (group)
[private]
requirements-dev group args="":
    @just uv " \
        export \
        --no-config \
        --no-emit-project \
        --quiet \
        --frozen \
        --no-dev \
        --only-group={{ group }}\
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
    rm -rf .just

# Clean the compiled translation file
[group("clean")]
clean-translation:
    find src/ -name *.mo -type f -delete

# Clean the source distribution and wheel directory
[group("clean")]
clean-dist:
    rm -rf dist

[group("clean")]
clean-uv-cache:
    @just uv "cache prune"

[group("clean")]
clean-coverage:
    rm -f ".just/.coverage*"

# Clean everything
[group("clean")]
clean-all:
    @just clean-coverage
    @just clean-python
    @just clean-BOM
    @just clean-just
    @just clean-docs
    @just clean-translation
    @just clean-dist

# Run a receipt for all Python versions (found in the .python-versions file). Works for all receipt whose first argument is a Python version
[group("tests")]
for-all-python receipt args="":
    for python in $(grep -v '^#' .python-versions); do \
        just {{ receipt }} $python {{ args }}; \
    done

# pip freeze
[private]
freeze receipt python dist resolution:
    @just uv " \
        pip freeze \
            --system \
            --python='\
                .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv\
            ' \
        | tee .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/requirements.txt \
    "

# pip install
[private]
install receipt python group link_mode = "":
    rm -f .just/{{ receipt }}/{{ python }}/requirements.txt
    @just requirements {{ group }}" \
        --output-file='\
            .just/{{ receipt }}/{{ python }}/requirements.txt\
        ' \
        --python='\
            .just/{{ receipt }}/{{ python }}/.venv\
        ' \
    "
    @just uv " \
        pip install  \
            --quiet \
            --exact \
            --strict \
            --require-hashes \
            {{ if link_mode == '' { '' } else { '--link-mode=' + link_mode } }} \
            --requirements='\
                .just/{{ receipt }}/{{ python }}/requirements.txt\
            ' \
            --prefix='\
                .just/{{ receipt }}/{{ python }}/.venv\
            ' \
            --python='\
                .just/{{ receipt }}/{{ python }}/.venv\
            ' \
    "

# pip install distribution
[private]
install-dist receipt python group dist resolution="highest" link_mode="":
    rm -f .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/requirements-dev.txt
    @just requirements-dev {{ group }}" \
        --output-file='\
            .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/requirements-dev.txt\
        ' \
        --python='\
            .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv\
        ' \
    "
    @just uv " \
        pip install {{ dist }} \
            --quiet \
            --exact \
            --strict \
            --resolution={{ resolution }} \
            {{ if link_mode == '' { '' } else { '--link-mode=' + link_mode } }} \
            --requirements='\
                .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/requirements-dev.txt\
            ' \
            --prefix='\
                .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv\
            ' \
            --python='\
                .just/{{ receipt }}-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv\
            ' \
    "
    @just freeze {{ receipt }} {{ python }} {{ dist }} {{ resolution }}

# Run the tests with pytest for a given Python and distribution for a given resolution.
[group("tests")]
test-dist python dist resolution="highest" link_mode="": (venv ("test-dist-" + resolution) python dist)
    rm -f ".just/.coverage.{{ arch() }}-{{ os() }}-{{ python }} .just/.coverage"
    @just install-dist test-dist {{ python }} tests {{ dist }} {{ resolution }} {{ link_mode }}
    TMPDIR="\
        {{ justfile_directory() }}/.just/test-dist-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/tmp\
    " \
    COVERAGE_FILE="\
        .just/.coverage.dist.{{ arch() }}-{{ os() }}-{{ python }}-{{ resolution }}\
    " \
    .just/test-dist-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv\
    /bin/python -m pytest \
        --html='\
            .just/.test_report.{{ python }}.{{ dist }}.{{ resolution }}.html\
        ' \
        --junitxml='\
            .just/.junit-{{ arch() }}-{{ os() }}-{{ dist }}-{{ resolution }}-{{ python }}.xml\
        ' \
        --md-report-output='\
            .just/.test_report_{{ python }}_{{ dist }}_{{ resolution }}.md\
        ' \
        --basetemp='\
            .just/test-dist-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/tmp\
        ' \
        --cov-config='.coveragerc' \
        'src' \
        'tests'

# Run the tests with pytest for lowest and highest resolutions
[group("tests")]
test-dist-lh python dist link_mode="":
    @just test-dist {{ python }} {{ dist }} lowest {{ link_mode }}
    @just test-dist {{ python }} {{ dist }} highest {{ link_mode }}

# Run the tests with pytest for a given Python
[group("tests")]
test-repository python: (venv "test-repo" python)
    rm -f ".just/.coverage.{{ arch() }}-{{ os() }}-{{ python }} .just/.coverage"
    @TMPDIR="{{ justfile_directory() }}/.just/test-repo/{{ python }}/tmp/" \
    COVERAGE_FILE="\
        .just/.coverage.repository.{{ arch() }}-{{ os() }}-{{ python }}\
    " \
    just uvr " \
        --group=tests \
        --python='\
            .just/test-repo/{{ python }}/.venv\
        ' \
    pytest \
        --html='\
            .just/.test_report.{{ python }}.html\
        ' \
        --junitxml='\
            .just/.junit-{{ arch() }}-{{ os() }}-{{ python }}.xml\
        ' \
        --md-report-output='\
            .just/.test_report_{{ python }}.md\
        ' \
        --basetemp=".just/test-repo/{{ python }}/tmp" \
        --cov-config=".coveragerc" \
        "src" \
        "tests" \
    "
    @just uvx "pyclean ."

alias test := test-repository

# Open a test report in a web browser
[group("report")]
open-test-report python dist="" resolution="highest":
    @[ "{{ dist }}" = "" ] \
        && ([ -f ".just/.test_report.{{ python }}.html" ] || just test-repository {{ python }}) \
        || ([ -f ".just/.test_report.{{ python }}.{{ dist }}.{{ resolution }}.html" ] || just test-dist {{ python }} {{ dist }} {{ resolution }})
    $BROWSER ".just/.test_report.{{ python }}.html"

[group("report")]
open-coverage-report:
    @[ -f ".just/coverage/htmlcov/index.html" ] || just coverage-report
    $BROWSER ".just/coverage/htmlcov/index.html"

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
check-types-dist python dist resolution="highest" link_mode="": (venv ("check-types-dist-" + resolution) python dist)
    @just install-dist check-types-dist {{ python }} check-types {{ dist }} {{ resolution }} {{ link_mode }}
    @just pyright " \
        --pythonpath=$( \
            uv python find \
            .just/check-types-dist-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv \
        ) \
        --project='pyrightconfig.json' \
        $( \
            uv run --no-project --python .just/check-types-dist-{{ resolution }}/{{ file_stem(dist) }}/{{ python }}/.venv \
            python -c "import sys,re,os,importlib.metadata as m; w=sys.argv[1]; d=re.match(r'(.*)-\d',os.path.basename(w)).group(1); dist=m.distribution(d); t=(dist.read_text('top_level.txt') or d).splitlines()[0]; print(os.path.abspath(os.path.join(dist.locate_file(''),t)))" \
            {{ dist }} \
        ) \
    "

# Run the type correctness with Pyright for a given Python for both lowest and highest resolutions
[group("tests")]
check-types-dist-lh python dist link_mode="":
    @just check-types-dist {{ python }} {{ dist }} lowest {{ link_mode }}
    @just check-types-dist {{ python }} {{ dist }} highest {{ link_mode }}

# Check the types corectness with Pyright for a given Python
[group("tests")]
check-types-repository python link_mode="": (venv "check-types" python)
    @just install check-types {{ python }} tests {{ link_mode }}
    @just pyright " \
        --pythonversion=$(uv run --no-project --python {{ python }} python --version | cut -d' ' -f2) \
        --venvpath=.just/check-types/{{ python }} \
        --project='pyrightconfig.json' \
        src/ tests/ docs/ \
    "

alias check-types := check-types-repository

# Print the dependency tree for a given Python
[group("dependencies")]
print-dependency-tree python: (venv "print-dependency-tree" python)
    uv tree \
        --python=".just/print-dependency-tree/{{ python }}/.venv" \
        --frozen \
        --no-dev

# Print the outdated dependencies for a given Python
[group("dependencies")]
print-outdated-direct-dependencies python: (venv "print-outdated-direct-dependencies" python)
    uv tree \
        --python=".just/print-outdated-direct-dependencies/{{ python }}/.venv" \
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
    @[ "$(find .just -maxdepth 1 -type f -name '.coverage.*')" ] \
        || just for-all-python test-repository
    @just uvr " \
        --directory='.just' \
        --only-group=coverage \
    coverage combine \
        --rcfile='.coveragerc' \
        --data-file=.coverage \
    "

# Report coverage in various formats (lcov, html, xml)
[group("report")]
coverage-report:
    @[ -f ".just/.coverage" ] || \
        just coverage-combine
    @just uvr " \
        --only-group=coverage \
    coverage html \
        --rcfile='.coveragerc' \
        --directory='.just/coverage/htmlcov' \
        --data-file='.just/.coverage' \
    "
    @just uvr " \
        --only-group=coverage \
    coverage lcov \
        --rcfile='.coveragerc' \
        -o='.just/coverage.lcov' \
        --data-file='.just/.coverage' \
    "
    @just uvr " \
        --only-group=coverage \
    coverage xml \
        --rcfile='.coveragerc' \
        -o='.just/coverage.xml' \
        --data-file='.just/.coverage' \
    "

# Print coverage
[group("coverage")]
coverage args="":
    @[ -f ".just/.coverage" ] || \
        just coverage-combine
    @just uvr " \
        --only-group=coverage \
    coverage report \
        --rcfile='.coveragerc' \
        --data-file='.just/.coverage' \
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
BOM-vulnerabilities python resolution="lowest":
    [ -d "BOM" ] || \
        mkdir -p "BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}"
    @just compile " \
        --resolution={{ resolution }} \
        --output-file '\
            BOM/vulnerabilities-{{ arch() }}-{{ os() }}-{{ python }}/\
            requirements.txt\
        ' \
        pyproject.toml \
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
        --resolution={{ resolution }} \
        --output-file '\
            .just/check-supply-chain-{{ resolution }}/{{ python }}/tmp/requirements.txt\
        ' \
        pyproject.toml \
    "
    @just pip-audit " \
        --requirement '\
            .just/check-supply-chain-{{ resolution }}/{{ python }}/tmp/requirements.txt\
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
        '.just/sphinx-autobuild/tmp/docs_build/' \
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
