# Artifact-Scythe

> Reclaim disk space by harvesting the build artifacts you forgot about.

[![CI](https://github.com/elielMengue/scythe/actions/workflows/ci.yml/badge.svg)](https://github.com/elielMengue/scythe/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/artifact-scythe.svg)](https://pypi.org/project/artifact-scythe/)
[![Python versions](https://img.shields.io/pypi/pyversions/artifact-scythe.svg)](https://pypi.org/project/artifact-scythe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


![Demo](demo/demo.gif)

[MP4 version](demo/demo.mp4)

`scythe` is a Python CLI that walks your projects directory, identifies each
project's ecosystem (Node, Python, Rust, Java, Go, Ruby, .NET) from its
marker files, and locates the bulky build artifacts that ecosystem leaves
behind — `node_modules`, `.venv`, `__pycache__`, `target/`, `build/`, and
the rest. It reports how much space each one is wasting and, when you tell
it to, deletes them.

It is safe by default: every `clean` previews what is about to happen and
asks for confirmation, and a `--dry-run` mode lets you check the plan
before running for real.

## Why

A laptop used daily for a year typically holds 30–80 GB of stale
`node_modules`, abandoned virtualenvs, cached compiler output, and CI
scratch directories. None of it is load-bearing — but finding and removing
it by hand across dozens of project folders is tedious and error-prone.
`scythe` does it in two commands.

## Quick start

```bash
pipx install artifact-scythe          # one-line global install

scythe scan ~/projects                # see what's eating your disk
scythe clean ~/projects --dry-run     # preview the deletions
scythe clean ~/projects               # do it (with confirmation)
```

## Install

### With `pipx` (recommended)

[`pipx`](https://pipx.pypa.io/) installs `scythe` into its own isolated
virtual environment and exposes the `scythe` command globally on your
`PATH`. It's the right tool for Python CLIs: no clash with your project
deps, no `sudo`, one command to upgrade.

```bash
pipx install artifact-scythe          # install
pipx upgrade artifact-scythe          # update later
pipx uninstall artifact-scythe        # remove cleanly
```

Don't have `pipx` yet? `python -m pip install --user pipx && python -m pipx ensurepath`
(restart your shell once).

### With `pip`

If you don't want the isolated install, plain `pip` works too:

```bash
pip install --user artifact-scythe    # user-level install
```

### Naming note

The PyPI distribution is `artifact-scythe` (the `scythe` slot on PyPI was
taken), but the installed command and the Python module are both `scythe`.
Scripts written against `scythe ...` keep working unchanged.

### With Docker

If you'd rather not install anything locally (CI agents, throwaway VMs,
or just trying it out), the official image is published on GHCR for both
`linux/amd64` and `linux/arm64`:

```bash
# scan the current directory
docker run --rm -v "$PWD":/work ghcr.io/elielmengue/scythe:latest scan /work

# clean with a dry-run
docker run --rm -v "$PWD":/work ghcr.io/elielmengue/scythe:latest \
    clean /work --dry-run
```

Tags follow the PyPI release: `:latest`, `:0.5.2`, `:0.5`, `:0`. The
rolling `:edge` tag tracks `main`.

### From source

```bash
git clone https://github.com/elielMengue/scythe.git
cd scythe
pip install -e ".[dev]"
```

## Usage

### `scythe scan` — discover projects and measure artifacts

```bash
scythe scan .                                  # current directory
scythe scan ~/dev --depth 2                    # bound recursion depth
scythe scan ~/dev --only node,python           # filter by ecosystem
scythe scan ~/dev --older-than 30              # only artifacts older than 30 days
scythe scan ~/dev --format tree                # table | tree | compact | json
scythe scan ~/dev --format json -o report.json # also csv via .csv suffix
```

`scan` is read-only. It produces a report; nothing is deleted.

### `scythe clean` — delete detected artifacts

```bash
scythe clean ~/dev --dry-run                   # simulate (always do this first)
scythe clean ~/dev --interactive               # pick projects manually
scythe clean ~/dev --only rust                 # only Rust target/ directories
scythe clean ~/dev --older-than 30 --dry-run   # only target stale artifacts
scythe clean ~/dev --force                     # skip the confirmation prompt
scythe clean ~/dev -o run-report.json          # export a JSON report
```

`clean` runs the same scan first, prints a summary, then either prompts
before deleting or executes immediately depending on flags. **Deletion
is permanent — files are not moved to the trash.**

### `scythe info`

Prints the installed version and the list of supported ecosystems and
patterns.

## Supported ecosystems

| Ecosystem      | Marker files                                                              | Artifact patterns                                                                                              |
|----------------|---------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| Node.js        | `package.json`, `yarn.lock`, `pnpm-lock.yaml`                             | `node_modules`, `dist`, `build`, `.next`, `.nuxt`, `out`, `.cache`, `.parcel-cache`, `.turbo`, `coverage`       |
| Python         | `requirements.txt`, `setup.py`, `pyproject.toml`, `Pipfile`, `poetry.lock`| `.venv`, `venv`, `env`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `*.egg-info`, `dist`, `build`, `.eggs`, `htmlcov` |
| Rust           | `Cargo.toml`, `Cargo.lock`                                                | `target`                                                                                                        |
| Java (Maven)   | `pom.xml`                                                                 | `target`, `.m2/repository`                                                                                      |
| Java (Gradle)  | `build.gradle`, `build.gradle.kts`, `settings.gradle`                     | `build`, `.gradle`, `out`                                                                                       |
| Go             | `go.mod`, `go.sum`                                                        | `bin`, `pkg`, `vendor`                                                                                          |
| Ruby           | `Gemfile`, `Gemfile.lock`, `.ruby-version`                                | `vendor/bundle`, `.bundle`, `tmp`                                                                               |
| .NET           | `*.csproj`, `*.fsproj`, `*.vbproj`, `*.sln`                               | `bin`, `obj`, `packages`, `.vs`                                                                                 |

The `--only` flag accepts both canonical names (`node`, `python`,
`java_maven`, `java_gradle`, `dotnet`, ...) and short aliases (`py`,
`js`, `rs`, `golang`, `.net`, `cs`).

## Safety

- `clean` deletes via `shutil.rmtree` / `Path.unlink` — files are gone,
  not in the trash bin. Run `--dry-run` first when in doubt.
- Source-control dirs (`.git`, `.svn`, `.hg`, `.bzr`), editor metadata
  (`.idea`, `.vscode`), and OS metadata (`.DS_Store`, `Thumbs.db`) are
  skipped during traversal.
- Symlinks are not followed unless `--follow-symlinks` is passed.
- Use `--depth N` on very large filesystems to avoid runaway scans.

## Development

Python 3.10+ is required.

```bash
git clone https://github.com/elielMengue/scythe.git
cd scythe
pip install -e ".[dev]"

pytest -v                       # full test suite
pytest --cov=scythe             # with coverage
pytest tests/test_scanner.py    # a single file
```

CI runs the test suite on Linux, macOS, and Windows for Python 3.10,
3.11, and 3.12. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Contributing

Issues and pull requests are welcome.

To add support for a new ecosystem, extend two places:

- `PROJECT_MARKERS` in [`scythe/scanner/scanner.py`](scythe/scanner/scanner.py) — how to recognise the project.
- `ARTIFACT_PATTERNS` in [`scythe/detector/detector.py`](scythe/detector/detector.py) — what to clean.

Then add a fixture and an assertion in `tests/test_detector.py` that
exercises the new pattern. Keeping these two maps in sync is the core
invariant of the codebase.

## Roadmap

- [x] Configuration & foundations
- [x] Directory scanner
- [x] Artifact detection
- [x] Rich-based UI (table / tree / compact / JSON)
- [x] Cleaning engine (`--dry-run`, `--interactive`, `--force`, JSON report)
- [x] Advanced features — *in progress* (`--only`, `--older-than` shipped; planned: `--min-size`, `--ignore`, trash-mode)
- [ ] Comprehensive tests & validation
- [ ] Broader distribution (Homebrew tap, Scoop)

See [CHANGELOG.md](CHANGELOG.md) for the release history.

## License

[MIT](LICENSE) © [Eliel MENGUE](https://github.com/elielMengue)
