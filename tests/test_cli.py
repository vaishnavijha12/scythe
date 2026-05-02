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

    def fake_clean_artifacts(projects, dry_run=False, progress_callback=None):
        captured["projects"] = projects
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
