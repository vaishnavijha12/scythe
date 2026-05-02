"""
Test for cleaner
"""

import pytest
from pathlib import Path
from datetime import datetime
from scythe.models.models import ArtifactInfo, Project, ProjectType
from scythe.cleaner.cleaner import ArtifactCleaner, clean_artifacts, safe_delete

@pytest.fixture
def temp_artifact(tmp_path):
    """Temporary artifact for testing"""
    artifact_dir = tmp_path / "node_modules"
    artifact_dir.mkdir()

    (artifact_dir / "package1").mkdir()
    (artifact_dir / "package1" / "index.js").write_text("module.exports = {}")
    (artifact_dir / "package2").mkdir()
    (artifact_dir / "package2" / "lib.js").write_text("exports.lib = {}")

    return artifact_dir
@pytest.fixture
def project_with_artifact(temp_artifact) :
    """Create temporary project for testing"""
    project_path = temp_artifact.parent

    artifact = ArtifactInfo(
        path=temp_artifact,
        size_bytes=1024 * 100,  # 100 KB
        last_modified=datetime.now(),
        artifact_type="node_modules"
    )

    project = Project(
        path=project_path,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact]
    )

    return project


def test_clean_artifact_dry_run(project_with_artifact):
    """Test in dry-run mode"""
    cleaner = ArtifactCleaner(dry_run=True)
    artifact = project_with_artifact.artifacts[0]

    assert artifact.path.exists()
    result = cleaner.clean_artifact(artifact)

    assert result == True
    assert cleaner.artifacts_deleted == 1
    assert cleaner.space_freed == artifact.size_bytes

    assert artifact.path.exists()


def test_clean_artifact_real(project_with_artifact):
    """Test with real mode"""
    cleaner = ArtifactCleaner(dry_run=False)
    artifact = project_with_artifact.artifacts[0]

    assert artifact.path.exists()

    result = cleaner.clean_artifact(artifact)

    assert result == True
    assert cleaner.artifacts_deleted == 1

    assert not artifact.path.exists()


def test_clean_project(project_with_artifact):
    """cleaning project"""
    cleaner = ArtifactCleaner(dry_run=False)

    result = cleaner.clean_project(project_with_artifact)

    assert result == True
    assert cleaner.artifacts_deleted == 1


def test_clean_projects_multiple(tmp_path):
    """Cleaning multiple projects"""
    projects = []

    for i in range(2):
        project_dir = tmp_path / f"project-{i}"
        project_dir.mkdir()

        artifact_dir = project_dir / "node_modules"
        artifact_dir.mkdir()
        (artifact_dir / "lib.js").write_text("code")

        artifact = ArtifactInfo(
            path=artifact_dir,
            size_bytes=1000,
            last_modified=datetime.now(),
            artifact_type="node_modules"
        )

        project = Project(
            path=project_dir,
            project_type=ProjectType.NODE,
            artifacts=[artifact]
        )

        projects.append(project)

    cleaner = ArtifactCleaner(dry_run=False)
    clean_result = cleaner.clean_projects(projects)

    assert clean_result.artifacts_deleted == 2
    assert len(clean_result.projects_cleaned) == 2


def test_clean_artifact_already_deleted(project_with_artifact):
    """Test with artifacts already deleted"""
    cleaner = ArtifactCleaner()
    artifact = project_with_artifact.artifacts[0]
    import shutil
    shutil.rmtree(artifact.path)

    result = cleaner.clean_artifact(artifact)

    assert result == False
    assert len(cleaner.skipped) == 1


def test_safe_delete_directory(tmp_path):
    """Test safe_delete"""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    assert test_dir.exists()

    result = safe_delete(test_dir, dry_run=False)

    assert result == True
    assert not test_dir.exists()


def test_safe_delete_file(tmp_path):
    """Test safe_delete with files"""
    test_file = tmp_path / "file.txt"
    test_file.write_text("content")

    assert test_file.exists()

    result = safe_delete(test_file, dry_run=False)

    assert result == True
    assert not test_file.exists()


def test_clean_with_trash_mover_routes_through_trash(tmp_path):
    """When a TrashMover is supplied, artifacts are moved instead of unlinked."""
    from scythe.trash import TrashMover, restore_run

    project_dir = tmp_path / "demo"
    artifact_dir = project_dir / "node_modules"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "package.json").write_text("{}")

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=2048,
        last_modified=datetime.now(),
        artifact_type="node_modules",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact],
    )

    mover = TrashMover(root=tmp_path / "scythe-data")
    result = clean_artifacts([project], dry_run=False, trash_mover=mover)
    manifest_path = mover.finalize(scan_path=project_dir)

    assert result.artifacts_deleted == 1
    assert result.space_freed == 2048
    assert not artifact_dir.exists()
    assert manifest_path.exists()

    # The package contents survived the move and a restore puts them back
    summary = restore_run(manifest_path)
    assert summary["restored"] == [str(artifact_dir)]
    assert (artifact_dir / "package.json").read_text() == "{}"


def test_clean_with_trash_mover_records_metadata(tmp_path):
    """Manifest carries artifact_type and project_type from the cleaner."""
    from scythe.trash import TrashMover, load_manifest

    project_dir = tmp_path / "rusty"
    artifact_dir = project_dir / "target"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "build.rs").write_text("// hi")

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=128,
        last_modified=datetime.now(),
        artifact_type="target",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.RUST,
        marker_files=["Cargo.toml"],
        artifacts=[artifact],
    )

    mover = TrashMover(root=tmp_path / "scythe-data")
    clean_artifacts([project], dry_run=False, trash_mover=mover)
    manifest_path = mover.finalize(scan_path=project_dir)

    data = load_manifest(manifest_path)
    assert len(data["items"]) == 1
    assert data["items"][0]["artifact_type"] == "target"
    assert data["items"][0]["project_type"] == "rust"


def test_clean_dry_run_with_trash_mover_does_not_move(tmp_path):
    """Dry-run should win even when --trash is set; nothing on disk changes."""
    from scythe.trash import TrashMover

    project_dir = tmp_path / "demo"
    artifact_dir = project_dir / "node_modules"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "package.json").write_text("{}")

    artifact = ArtifactInfo(
        path=artifact_dir,
        size_bytes=10,
        last_modified=datetime.now(),
        artifact_type="node_modules",
    )
    project = Project(
        path=project_dir,
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[artifact],
    )

    mover = TrashMover(root=tmp_path / "scythe-data")
    result = clean_artifacts([project], dry_run=True, trash_mover=mover)

    assert result.artifacts_deleted == 1
    assert artifact_dir.exists()
    assert not (tmp_path / "scythe-data" / "trash").exists()