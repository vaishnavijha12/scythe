# Contributing to Artifact-Scythe

Thanks for your interest in contributing. This guide gets you from a fresh
clone to a merged PR.

## Quick links

- [Issues](https://github.com/elielMengue/scythe/issues) — bugs and feature
  requests, including a `good first issue` label for newcomers.
- [CHANGELOG.md](CHANGELOG.md) — release history, written user-first.
- [`scythe/scanner/scanner.py`](scythe/scanner/scanner.py) and
  [`scythe/detector/detector.py`](scythe/detector/detector.py) — the two
  files you most likely want to touch.

## Development setup

Python 3.10 or newer is required.

```bash
git clone https://github.com/elielMengue/scythe.git
cd scythe
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest -v                       # full suite
pytest --cov=scythe             # with coverage
pytest tests/test_scanner.py    # one file
pytest -k "test_only_filter"    # one match by keyword
```

Smoke-test the installed CLI on the repo itself:

```bash
scythe --version
scythe info
scythe scan . --depth 1
```

## How the codebase fits together

The pipeline is **scan -> detect -> (optional) clean**. Every stage operates
on dataclasses defined in [`scythe/models/models.py`](scythe/models/models.py)
(`ProjectType`, `ArtifactInfo`, `Project`, `ScanResult`, `CleanResult`).
Reading those types is the fastest path to understanding the rest.

| Module | What it owns |
|---|---|
| `scythe/cli.py` | Click command tree, Rich rendering, top-level options |
| `scythe/scanner/scanner.py` | Recursive walk + project detection (`PROJECT_MARKERS`) |
| `scythe/detector/detector.py` | Artifact discovery per ecosystem (`ARTIFACT_PATTERNS`) |
| `scythe/cleaner/cleaner.py` | `shutil.rmtree` / `Path.unlink`, error and skip tracking |
| `scythe/ui/ui.py` | Tables, trees, progress bars, interactive prompts |
| `scythe/formatter/formatter.py` | JSON / CSV report serialisation |
| `scythe/logger/logger.py` | Rich console handler + optional file log |

## Adding support for a new ecosystem

This is the most common contribution and the cleanest "good first issue".
You need to extend two maps and add tests:

1. **Marker files** — add an entry to `PROJECT_MARKERS` in
   `scythe/scanner/scanner.py`. Glob patterns like `*.csproj` are supported.
2. **Artifact patterns** — add an entry to `ARTIFACT_PATTERNS` in
   `scythe/detector/detector.py`.
3. **Tests** — add a fixture in `tests/test_detector.py` that creates a
   minimal project of the new type and asserts that `detect_artifacts`
   finds the expected directories. Mirror the style of the existing
   Node and Python fixtures.

Keeping `PROJECT_MARKERS` and `ARTIFACT_PATTERNS` in sync is the core
invariant of the codebase — if you add markers without artifacts (or the
reverse) the project is detected but nothing is cleaned, and vice-versa.

## Pull requests

- Branch from `main`, keep PRs focused (one logical change per PR).
- Tests must pass on Linux, macOS and Windows for Python 3.10 / 3.11 /
  3.12 — the CI matrix runs all of that automatically; check the run
  before requesting review.
- Add a CHANGELOG entry under an `## [Unreleased]` section, or under the
  next planned version. Maintainer will move it on release.
- Commit messages: imperative, scoped, no emoji. Example:
  `cleaner: skip read-only files instead of failing`.
- No need to bump the version yourself — that happens at release time.

## Reporting bugs

Open an issue with:

- The output of `scythe --version` and `python --version`.
- Your operating system.
- The exact command you ran and what you expected versus what happened.
- If a scan or clean was involved, attach the relevant section of
  `logs/scyth_*.log` (the file scythe writes by default unless you pass
  `--no-log-file`).

## Release process (maintainer only)

1. Bump `version` in `pyproject.toml` and `__version__` in
   `scythe/__init__.py` (must match).
2. Move the unreleased CHANGELOG entry under a new dated heading.
3. Commit on `main`: `Release vX.Y.Z - <summary>`.
4. Tag annotated: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`.
5. Push: `git push origin main && git push origin vX.Y.Z`.
6. The `release.yml` workflow builds the sdist + wheel, publishes to
   PyPI via Trusted Publishing (OIDC, no token), and creates a GitHub
   Release with auto-generated notes.

## Code of conduct

Be kind. Assume good intent. We follow the spirit of the
[Contributor Covenant](https://www.contributor-covenant.org/).

## License

By contributing you agree that your contributions are licensed under the
project's [MIT license](LICENSE).
