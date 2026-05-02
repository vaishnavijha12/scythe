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
