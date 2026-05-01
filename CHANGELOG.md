# Changelog

## [0.1.0] - 2025-01-29

### Added
- Initial CLI structure with Click
- Rich logging system (console + file)
- Basic commands: scan, clean, info
- Unit tests for CLI 
- Project documentation

##  [0.1.0] - 2025-01-30

### Changed 

-   setup.py -> pyproject.toml

### Added 

-   Scan Feature
  - Test for scan and models


## [0.2.0] - 2025-01-31

### Added
-  **Directory Scanner** - Scan récursif de répertoires
-  **Project Detection** - Détection automatique de 8 types de projets :
  - Node.js (package.json, yarn.lock, pnpm-lock.yaml)
  - Python (requirements.txt, setup.py, pyproject.toml, Pipfile)
  - Rust (Cargo.toml)
  - Java Maven (pom.xml)
  - Java Gradle (build.gradle)
  - Go (go.mod)
  - Ruby (Gemfile)
  - .NET (*.csproj, *.sln)


### Fixed
- Logger initialization avec arguments corrects
- RichHandler typo (`tracebacks_show_locals`)
- Project dataclass avec `project_type` (singulier)
- DateTime default factory pour éviter les erreurs de mutation

### Technical
- Scan with configurable depth (`--depth`)
- Erros handling (permissions, chemins invalides)
- Patterns ignored (.git, .svn, .idea, etc.)

### Coming Next
- [x] Detection and calculation of artefacts (node_modules, .venv, target/, etc.) **Done**

## [0.2.0] - 2025-02-02

### Added 
- Artifact detector and size calculation

## [0.2.0] - 2025-05-02

### Added

- Scan format (tree, table, json)
- Report generation in two formats (csv & json) 
- Add new option to the cli : command example `scythe scan /project_path --format [tree, table, json]` this helps format the scan result in a better way we want it to.
`scythe scan /project_path --output report_file` this command will generate a report after the scan complete. Notice that the report file support only two types : **csv** and **json**
- Release v0.3.0

## [0.5.1] - 2026-05-01

### Changed
- **PyPI distribution renamed** to `artifact-scythe` (the name `scythe` is taken
  on PyPI). The Python module and the installed command remain `scythe`,
  so user-facing usage is unchanged. Install becomes `pip install artifact-scythe`.
- README badges and install snippet updated accordingly. Release workflow
  environment URL points at https://pypi.org/p/artifact-scythe.

### Fixed
- **Windows CI smoke test** crashed with `UnicodeEncodeError` on cp1252
  when Rich rendered the braille spinner (`U+2838`) and box-drawing
  characters. Setting `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` at the
  workflow level forces UTF-8 stdio across all jobs. Reproduced and
  validated locally on Windows 11.
- `banner.VERSION` was hardcoded to `0.3.0`; now mirrors
  `scythe.__version__` so `scythe info` reports the real version.
- Banner ASCII art switched to a raw string to silence the
  invalid-escape `SyntaxWarning` raised on Python 3.12+.

### Technical
- First release pipeline run end-to-end (CI matrix → PyPI publish via
  Trusted Publishing → GitHub Release with auto-generated notes).
- Release v0.5.1

## [0.5.0] - 2026-05-01

### Added
- **`--only TYPES` filter** on both `scan` and `clean` commands. Accepts a
  comma-separated list of project types (canonical values like `node`,
  `python`, `rust`, `java_maven`, `java_gradle`, `go`, `ruby`, `dotnet`, or
  short aliases like `py`, `js`, `rs`, `golang`, `.net`, `cs`).
  - Example: `scythe clean ~/projects --only node,python --dry-run`
- `ProjectType.from_alias` classmethod that resolves a user-supplied string
  to a `ProjectType`, raising a clear error listing valid types on a typo.
- Unit tests covering canonical names, short aliases, case/whitespace
  insensitivity, and the unknown-alias error path.

### Fixed
- **Critical scanner bug**: `_scan_recursive` used `global project, artifacts`
  and unconditionally appended `project` even when the current directory had
  no marker file. This raised `NameError` on the first call for any non-project
  root, which was silently swallowed by the outer try/except so users saw 0
  projects with no surface error. Rewritten to use local variables and only
  append when a project is actually detected.
- Renamed test fixture `node_project_with_artifact` → `node_project_with_artifacts`
  so that `test_detect_artifacts_node` resolves correctly.

### Technical
- Test suite: 29 → 33 passing.
- Release v0.5.0

## [0.4.0] - 2026-02-06

### Added
- **Cleaning Engine** - Real artifact deletion built on top of the scanner/detector pipeline
  - `ArtifactCleaner` class handles per-project and per-artifact removal with full error/skip tracking
  - `CleanResult` dataclass aggregates deletion stats (artifacts deleted, space freed, success rate, duration)
  - `safe_delete` helper for one-off path removal
- **`scythe clean` CLI command** with the following modes:
  - `--dry-run` : simulation, reports what would be freed without touching the disk
  - `--interactive` / `-i` : manual selection of projects to clean
  - `--force` / `-f` : skip confirmation prompt (for scripts/automation)
  - `--depth` / `-d` : bound the preliminary scan
  - `--output` / `-o` : export a JSON report of the clean run
- Two-step UX: scan first, then confirm before deletion. Summary table rendered with Rich (cleaned projects, artifacts deleted, freed memory, success rate, errors, skipped).
- Unit tests for the cleaner (`tests/test_cleaner.py`)

### Technical
- Permission/OSError/unknown-error paths are captured in `CleanResult.errors` instead of raising
- Missing artifacts at deletion time are recorded in `CleanResult.skipped` rather than failing
- Release v0.4.0
