from contextlib import contextmanager
from datetime import datetime
import importlib
import logging
from pathlib import Path

from click.testing import CliRunner

from scythe.models.models import ArtifactInfo, CleanResult, Project, ProjectType, ScanResult

cli_module = importlib.import_module("scythe.cli")


@contextmanager
def _fake_progress_bar():
    class _Progress:
        def add_task(self, *_args, **_kwargs):
            return 1

        def update(self, *_args, **_kwargs):
            return None

    yield _Progress()


def _project_with_small_and_large_artifacts(root: Path) -> Project:
    now = datetime(2026, 5, 2)
    return Project(
        path=root / "demo-project",
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[
            ArtifactInfo(
                path=root / "demo-project" / "small-cache",
                size_bytes=512,
                last_modified=now,
                artifact_type="cache",
            ),
            ArtifactInfo(
                path=root / "demo-project" / "node_modules",
                size_bytes=2 * 1024 * 1024,
                last_modified=now,
                artifact_type="node_modules",
            ),
        ],
    )


def test_scan_min_size_filters_artifacts(monkeypatch):
    captured = {}
    root = Path.cwd()
    result = ScanResult(root_path=root, projects=[_project_with_small_and_large_artifacts(root)])

    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-scan"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: result)
    monkeypatch.setattr(
        cli_module,
        "display_scan_result",
        lambda filtered_result, *_args, **_kwargs: captured.setdefault("result", filtered_result),
    )

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "scan", str(root), "--min-size", "1MB"],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0
    filtered = captured["result"]
    assert len(filtered.projects) == 1
    assert len(filtered.projects[0].artifacts) == 1
    assert filtered.projects[0].artifacts[0].artifact_type == "node_modules"
    assert filtered.projects[0].total_artifact_size == 2 * 1024 * 1024


def test_clean_min_size_filters_before_cleaning(monkeypatch):
    captured = {}
    root = Path.cwd()
    scan_result = ScanResult(root_path=root, projects=[_project_with_small_and_large_artifacts(root)])

    def fake_clean_artifacts(projects, dry_run=False, progress_callback=None, trash_mover=None):
        captured["projects"] = projects
        captured["trash_mover"] = trash_mover
        if progress_callback:
            for project in projects:
                progress_callback(f"Cleaning {project.path.name}")
        return CleanResult(
            projects_cleaned=projects,
            artifacts_deleted=sum(len(project.artifacts) for project in projects),
            space_freed=sum(project.total_artifact_size for project in projects),
            dry_run=dry_run,
        )

    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-clean"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)
    monkeypatch.setattr(cli_module, "clean_artifacts", fake_clean_artifacts)

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "clean", str(root), "--dry-run", "--min-size", "1MB"],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0
    assert "projects" in captured
    assert len(captured["projects"]) == 1
    assert len(captured["projects"][0].artifacts) == 1
    assert captured["projects"][0].artifacts[0].artifact_type == "node_modules"


def test_scan_rejects_invalid_min_size():
    root = Path.cwd()
    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "scan", str(root), "--min-size", "nope"],
    )

    assert invoke.exit_code != 0
    assert "Invalid value for --min-size" in invoke.output


def test_clean_trash_flag_routes_through_trash_mover(monkeypatch, tmp_path):
    """End-to-end: --trash builds a TrashMover, moves the artifact, writes a manifest."""
    project_dir = tmp_path / "demo"
    artifact_dir = project_dir / "node_modules"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "package.json").write_text("{}")

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=2048,
        last_modified=datetime(2026, 5, 2),
        artifact_type="node_modules",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact],
    )
    scan_result = ScanResult(root_path=project_dir, projects=[project])

    trash_root = tmp_path / "scythe-data"
    monkeypatch.setattr("scythe.trash.trash.get_trash_root", lambda: trash_root)
    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-trash"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "clean", str(project_dir), "--trash", "--force"],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output
    assert not artifact_dir.exists()

    runs = list((trash_root / "runs").glob("*.json"))
    assert len(runs) == 1
    import json
    manifest = json.loads(runs[0].read_text())
    assert len(manifest["items"]) == 1
    assert manifest["items"][0]["original_path"] == str(artifact_dir)
    assert manifest["items"][0]["project_type"] == "node"
    assert manifest["scan_path"] == str(project_dir)


def test_restore_list_when_no_runs(monkeypatch, tmp_path):
    monkeypatch.setattr("scythe.trash.trash.get_trash_root", lambda: tmp_path / "scythe-data")
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-restore-empty"))

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "restore", "--list"],
        catch_exceptions=False,
    )
    assert invoke.exit_code == 0
    assert "No recoverable runs" in invoke.output


def test_restore_default_undoes_most_recent_run(monkeypatch, tmp_path):
    """E2E: --trash → restore (no args) brings everything back."""
    project_dir = tmp_path / "demo"
    artifact_dir = project_dir / "node_modules"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "package.json").write_text('{"hello":1}')

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=11,
        last_modified=datetime(2026, 5, 2),
        artifact_type="node_modules",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact],
    )
    scan_result = ScanResult(root_path=project_dir, projects=[project])

    trash_root = tmp_path / "scythe-data"
    monkeypatch.setattr("scythe.trash.trash.get_trash_root", lambda: trash_root)
    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-restore"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    runner = CliRunner()

    clean_invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "clean", str(project_dir), "--trash", "--force"],
        catch_exceptions=False,
    )
    assert clean_invoke.exit_code == 0, clean_invoke.output
    assert not artifact_dir.exists()

    restore_invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "restore"],
        catch_exceptions=False,
    )
    assert restore_invoke.exit_code == 0, restore_invoke.output
    assert artifact_dir.exists()
    assert (artifact_dir / "package.json").read_text() == '{"hello":1}'


def test_restore_unknown_run_id_exits_nonzero(monkeypatch, tmp_path):
    trash_root = tmp_path / "scythe-data"
    (trash_root / "runs").mkdir(parents=True)
    # write a manifest so the "no runs" branch isn't hit
    (trash_root / "runs" / "20260101-000000-000000.json").write_text(
        '{"run_id": "20260101-000000-000000", "items": [], "started_at": "2026-01-01T00:00:00"}'
    )
    monkeypatch.setattr("scythe.trash.trash.get_trash_root", lambda: trash_root)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-restore-unknown"))

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "restore", "nope-not-a-real-id"],
        catch_exceptions=False,
    )
    assert invoke.exit_code == 1
    assert "No run with id" in invoke.output


def test_clean_csv_suffix_writes_csv(monkeypatch, tmp_path):
    """Regression for #6: clean -o report.csv must write CSV, not JSON."""
    project = _project_with_small_and_large_artifacts(tmp_path)
    # The cleaner skips artifacts whose path doesn't exist; materialize them.
    for artifact in project.artifacts:
        artifact.path.mkdir(parents=True, exist_ok=True)
    scan_result = ScanResult(root_path=tmp_path, projects=[project])

    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "scan_progress", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "clean_progress", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-csv"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    report_path = tmp_path / "run.csv"
    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        [
            "--no-log-file",
            "clean", str(tmp_path),
            "--dry-run", "--force",
            "-o", str(report_path),
        ],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output
    assert report_path.exists()

    content = report_path.read_text(encoding="utf-8")
    first_line = content.splitlines()[0]
    assert "path" in first_line
    assert "type" in first_line
    assert "space_freed_bytes" in first_line
    # Not an opening brace, which would indicate JSON.
    assert not content.lstrip().startswith("{")


def test_clean_json_suffix_writes_json(monkeypatch, tmp_path):
    """The .json suffix still routes to the JSON writer with the enriched schema."""
    project = _project_with_small_and_large_artifacts(tmp_path)
    for artifact in project.artifacts:
        artifact.path.mkdir(parents=True, exist_ok=True)
    scan_result = ScanResult(root_path=tmp_path, projects=[project])

    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "scan_progress", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "clean_progress", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-json"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    report_path = tmp_path / "run.json"
    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        [
            "--no-log-file",
            "clean", str(tmp_path),
            "--dry-run", "--force",
            "-o", str(report_path),
        ],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output
    assert report_path.exists()

    import json as _json
    payload = _json.loads(report_path.read_text(encoding="utf-8"))
    assert "summary" in payload
    assert "projects" in payload
    assert payload["projects"][0]["space_freed_bytes"] == 2 * 1024 * 1024 + 512


def test_quiet_scan_suppresses_decorative_output(monkeypatch, tmp_path):
    """--quiet should drop progress bars, run header and result table for scan."""
    scan_result = ScanResult(
        root_path=tmp_path,
        projects=[_project_with_small_and_large_artifacts(tmp_path)],
    )

    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-quiet-scan"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    def _fail(*_args, **_kwargs):
        raise AssertionError("decorative helper called in --quiet mode")

    monkeypatch.setattr(cli_module, "display_run_header", _fail)
    monkeypatch.setattr(cli_module, "display_scan_result", _fail)
    monkeypatch.setattr(cli_module, "scan_progress", _fail)

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "--quiet", "scan", str(tmp_path)],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output


def test_quiet_scan_still_writes_output_file(monkeypatch, tmp_path):
    """--quiet must not break --output: the report file is still written."""
    scan_result = ScanResult(
        root_path=tmp_path,
        projects=[_project_with_small_and_large_artifacts(tmp_path)],
    )

    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-quiet-output"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    report_path = tmp_path / "scan.json"
    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "--quiet", "scan", str(tmp_path), "-o", str(report_path)],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output
    assert report_path.exists()
    # No "report saved" decorative line in quiet mode.
    assert "report is saved" not in invoke.output.lower()


    def test_quiet_clean_suppresses_decorative_output(monkeypatch, tmp_path):
    """--quiet on clean drops headers, plan, footer; --output still works."""
    project = _project_with_small_and_large_artifacts(tmp_path)
    for artifact in project.artifacts:
        artifact.path.mkdir(parents=True, exist_ok=True)
    scan_result = ScanResult(root_path=tmp_path, projects=[project])

    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-quiet-clean"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    def _fail(*_args, **_kwargs):
        raise AssertionError("decorative helper called in --quiet mode")

    monkeypatch.setattr(cli_module, "display_run_header", _fail)
    monkeypatch.setattr(cli_module, "display_clean_plan", _fail)
    monkeypatch.setattr(cli_module, "display_clean_footer", _fail)
    monkeypatch.setattr(cli_module, "scan_progress", _fail)
    monkeypatch.setattr(cli_module, "clean_progress", _fail)

    report_path = tmp_path / "clean.json"
    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        [
            "--no-log-file", "--quiet",
            "clean", str(tmp_path),
            "--dry-run", "--force",
            "-o", str(report_path),
        ],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0, invoke.output
    assert report_path.exists()


    def test_clean_dry_run_skips_trash_setup(monkeypatch, tmp_path):
    """--dry-run + --trash should NOT create a trash dir or manifest."""
    project_dir = tmp_path / "demo"
    artifact_dir = project_dir / "node_modules"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "package.json").write_text("{}")

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=2048,
        last_modified=datetime(2026, 5, 2),
        artifact_type="node_modules",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact],
    )
    scan_result = ScanResult(root_path=project_dir, projects=[project])

    trash_root = tmp_path / "scythe-data"
    monkeypatch.setattr("scythe.trash.trash.get_trash_root", lambda: trash_root)
    monkeypatch.setattr(cli_module, "progress_bar", _fake_progress_bar)
    monkeypatch.setattr(cli_module, "setup_logger", lambda **_kwargs: logging.getLogger("test-trash-dry"))
    monkeypatch.setattr(cli_module, "scan_directory", lambda **_kwargs: scan_result)

    runner = CliRunner()
    invoke = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "clean", str(project_dir), "--trash", "--dry-run", "--force"],
        catch_exceptions=False,
    )

    assert invoke.exit_code == 0
    assert artifact_dir.exists()  # still here
    assert not trash_root.exists()
    def test_no_color_flag(monkeypatch, tmp_path):
    """--no-color disables ANSI colored output."""
    scan_result = ScanResult(
        root_path=tmp_path,
        projects=[],
    )

    monkeypatch.setattr(
        cli_module,
        "setup_logger",
        lambda **_kwargs: logging.getLogger("test-no-color-flag"),
    )
    monkeypatch.setattr(
        cli_module,
        "scan_directory",
        lambda **_kwargs: scan_result,
    )

    runner = CliRunner()

    result = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "--no-color", "scan", str(tmp_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "\x1b[" not in result.output


    def test_no_color_env(monkeypatch, tmp_path):
    """NO_COLOR env var disables ANSI colored output."""
    scan_result = ScanResult(
        root_path=tmp_path,
        projects=[],
    )

    monkeypatch.setenv("NO_COLOR", "1")

    monkeypatch.setattr(
        cli_module,
        "setup_logger",
        lambda **_kwargs: logging.getLogger("test-no-color-env"),
    )
    monkeypatch.setattr(
        cli_module,
        "scan_directory",
        lambda **_kwargs: scan_result,
    )

    runner = CliRunner()

    result = runner.invoke(
        cli_module.cli,
        ["--no-log-file", "scan", str(tmp_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "\x1b[" not in result.output
