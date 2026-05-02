"""
Tests for scythe.trash — the foundation for --trash and `scythe restore`.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from scythe.trash import (
    TrashMover,
    get_trash_root,
    list_runs,
    load_manifest,
    new_run_id,
    restore_run,
)


def test_get_trash_root_linux(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert get_trash_root() == tmp_path / "scythe"


def test_get_trash_root_linux_default(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    expected = Path.home() / ".local" / "share" / "scythe"
    assert get_trash_root() == expected


def test_get_trash_root_macos(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    expected = Path.home() / "Library" / "Application Support" / "scythe"
    assert get_trash_root() == expected


def test_get_trash_root_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert get_trash_root() == tmp_path / "scythe"


def test_new_run_id_is_sortable():
    a = new_run_id(datetime(2026, 5, 2, 10, 0, 0))
    b = new_run_id(datetime(2026, 5, 2, 10, 0, 1))
    assert a < b
    assert "20260502" in a


def test_trash_mover_moves_directory(tmp_path):
    source = tmp_path / "project" / "node_modules"
    source.mkdir(parents=True)
    (source / "package.json").write_text("{}")
    (source / "lodash").mkdir()

    mover = TrashMover(root=tmp_path / "scythe-data")
    dest = mover.move(source, size_bytes=42, artifact_type="node_modules", project_type="node")

    assert not source.exists()
    assert dest.exists()
    assert dest.is_dir()
    assert (dest / "package.json").read_text() == "{}"
    assert dest.parent == tmp_path / "scythe-data" / "trash" / mover.run_id
    assert dest.name == "0_node_modules"


def test_trash_mover_handles_name_collisions(tmp_path):
    """Two artifacts with the same basename should both be moved without clobbering."""
    a = tmp_path / "project_a" / "build"
    b = tmp_path / "project_b" / "build"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / "x.o").write_text("a")
    (b / "x.o").write_text("b")

    mover = TrashMover(root=tmp_path / "scythe-data")
    dest_a = mover.move(a, size_bytes=1, artifact_type="build", project_type="rust")
    dest_b = mover.move(b, size_bytes=1, artifact_type="build", project_type="rust")

    assert dest_a != dest_b
    assert dest_a.name == "0_build"
    assert dest_b.name == "1_build"
    assert (dest_a / "x.o").read_text() == "a"
    assert (dest_b / "x.o").read_text() == "b"


def test_trash_mover_finalize_writes_manifest(tmp_path):
    source = tmp_path / "project" / "target"
    source.mkdir(parents=True)
    (source / "build.rs").write_text("// hi")

    scan_root = tmp_path / "project"
    mover = TrashMover(root=tmp_path / "scythe-data")
    mover.move(source, size_bytes=128, artifact_type="target", project_type="rust")
    manifest_path = mover.finalize(scan_path=scan_root)

    assert manifest_path.exists()
    data = load_manifest(manifest_path)
    assert data["run_id"] == mover.run_id
    assert data["scan_path"] == str(scan_root)
    assert data["finished_at"] is not None
    assert data["restored_at"] is None
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["index"] == 0
    assert item["original_path"] == str(source)
    assert item["size_bytes"] == 128
    assert item["artifact_type"] == "target"
    assert item["project_type"] == "rust"


def test_trash_mover_finalize_with_no_items(tmp_path):
    mover = TrashMover(root=tmp_path / "scythe-data")
    manifest_path = mover.finalize()
    data = load_manifest(manifest_path)
    assert data["items"] == []


def test_list_runs_returns_newest_first(tmp_path):
    root = tmp_path / "scythe-data"

    m1 = TrashMover(run_id="20260501-100000-000000", root=root)
    m1.finalize()
    m2 = TrashMover(run_id="20260502-100000-000000", root=root)
    m2.finalize()
    m3 = TrashMover(run_id="20260503-100000-000000", root=root)
    m3.finalize()

    runs = list_runs(root=root)
    assert [r.stem for r in runs] == [
        "20260503-100000-000000",
        "20260502-100000-000000",
        "20260501-100000-000000",
    ]


def test_list_runs_when_empty(tmp_path):
    assert list_runs(root=tmp_path / "no-such-dir") == []


def test_restore_run_round_trip(tmp_path):
    project = tmp_path / "project"
    artifact = project / "node_modules"
    artifact.mkdir(parents=True)
    (artifact / "package.json").write_text("{}")

    mover = TrashMover(root=tmp_path / "scythe-data")
    mover.move(artifact, size_bytes=10, artifact_type="node_modules", project_type="node")
    manifest_path = mover.finalize()

    assert not artifact.exists()

    summary = restore_run(manifest_path)

    assert artifact.exists()
    assert (artifact / "package.json").read_text() == "{}"
    assert summary["restored"] == [str(artifact)]
    assert summary["skipped"] == []
    assert summary["errors"] == []

    data = load_manifest(manifest_path)
    assert data["restored_at"] is not None


def test_restore_run_skips_when_destination_exists(tmp_path):
    artifact = tmp_path / "project" / "node_modules"
    artifact.mkdir(parents=True)
    (artifact / "x.txt").write_text("original")

    mover = TrashMover(root=tmp_path / "scythe-data")
    mover.move(artifact, size_bytes=1, artifact_type="node_modules", project_type="node")
    manifest_path = mover.finalize()

    artifact.mkdir(parents=True)
    (artifact / "y.txt").write_text("recreated")

    summary = restore_run(manifest_path)

    assert summary["restored"] == []
    assert len(summary["skipped"]) == 1
    assert summary["skipped"][0]["reason"] == "destination already exists"
    assert (artifact / "y.txt").read_text() == "recreated"

    data = load_manifest(manifest_path)
    assert data["restored_at"] is None


def test_restore_run_skips_when_trash_entry_missing(tmp_path):
    artifact = tmp_path / "project" / "node_modules"
    artifact.mkdir(parents=True)

    mover = TrashMover(root=tmp_path / "scythe-data")
    trash_dest = mover.move(artifact, size_bytes=1, artifact_type="node_modules", project_type="node")
    manifest_path = mover.finalize()

    import shutil as _shutil

    _shutil.rmtree(trash_dest)

    summary = restore_run(manifest_path)
    assert summary["restored"] == []
    assert len(summary["skipped"]) == 1
    assert summary["skipped"][0]["reason"] == "trash entry missing"
