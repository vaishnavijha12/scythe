"""
Tests for scythe.utils.utils
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scythe.models.models import ArtifactInfo, Project, ProjectType
from scythe.utils.utils import (
    filter_projects_by_artifact_age,
    filter_projects_by_artifact_size,
    format_size,
    is_ignored_path,
    parse_size_threshold,
)


def _project(path: str, ages_days: list[int], now: datetime) -> Project:
    artifacts = [
        ArtifactInfo(
            path=Path(path) / f"artifact_{i}",
            size_bytes=100,
            last_modified=now - timedelta(days=age),
            artifact_type="node_modules",
        )
        for i, age in enumerate(ages_days)
    ]
    return Project(
        path=Path(path),
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=artifacts,
    )


def test_filter_zero_or_negative_returns_all():
    now = datetime(2026, 5, 1)
    projects = [_project("/a", [1, 60], now)]
    assert filter_projects_by_artifact_age(projects, 0, now=now) == projects
    assert filter_projects_by_artifact_age(projects, -5, now=now) == projects


def test_filter_drops_recent_only_projects():
    now = datetime(2026, 5, 1)
    recent = _project("/recent", [1, 5], now)
    old = _project("/old", [60, 90], now)
    result = filter_projects_by_artifact_age([recent, old], 30, now=now)
    assert len(result) == 1
    assert result[0].path == Path("/old")


def test_filter_keeps_only_old_artifacts_within_project():
    now = datetime(2026, 5, 1)
    mixed = _project("/mixed", [1, 60, 90], now)
    result = filter_projects_by_artifact_age([mixed], 30, now=now)
    assert len(result) == 1
    kept = result[0]
    assert len(kept.artifacts) == 2
    assert all((now - a.last_modified).days >= 30 for a in kept.artifacts)
    assert kept.total_artifact_size == 200


def test_filter_does_not_mutate_input():
    now = datetime(2026, 5, 1)
    mixed = _project("/mixed", [1, 60], now)
    original_count = len(mixed.artifacts)
    filter_projects_by_artifact_age([mixed], 30, now=now)
    assert len(mixed.artifacts) == original_count


def test_filter_boundary_exactly_at_cutoff():
    now = datetime(2026, 5, 1)
    boundary = _project("/edge", [30], now)
    result = filter_projects_by_artifact_age([boundary], 30, now=now)
    assert len(result) == 1


def test_filter_size_zero_or_negative_returns_all():
    now = datetime(2026, 5, 1)
    projects = [_project("/a", [1, 60], now)]
    assert filter_projects_by_artifact_size(projects, 0) == projects
    assert filter_projects_by_artifact_size(projects, -1) == projects


def test_filter_size_drops_small_only_projects():
    now = datetime(2026, 5, 1)
    small = Project(
        path=Path("/small"),
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[
            ArtifactInfo(
                path=Path("/small/a"),
                size_bytes=100,
                last_modified=now,
                artifact_type="node_modules",
            )
        ],
    )
    large = Project(
        path=Path("/large"),
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[
            ArtifactInfo(
                path=Path("/large/a"),
                size_bytes=10_000,
                last_modified=now,
                artifact_type="node_modules",
            )
        ],
    )

    result = filter_projects_by_artifact_size([small, large], 1000)
    assert len(result) == 1
    assert result[0].path == Path("/large")


def test_filter_size_keeps_only_large_artifacts_within_project():
    now = datetime(2026, 5, 1)
    project = Project(
        path=Path("/mixed"),
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[
            ArtifactInfo(
                path=Path("/mixed/small"),
                size_bytes=100,
                last_modified=now,
                artifact_type="cache",
            ),
            ArtifactInfo(
                path=Path("/mixed/large"),
                size_bytes=10_000,
                last_modified=now,
                artifact_type="node_modules",
            ),
        ],
    )

    result = filter_projects_by_artifact_size([project], 1000)
    assert len(result) == 1
    kept = result[0]
    assert len(kept.artifacts) == 1
    assert kept.artifacts[0].artifact_type == "node_modules"
    assert kept.total_artifact_size == 10_000


def test_filter_size_does_not_mutate_input():
    now = datetime(2026, 5, 1)
    project = Project(
        path=Path("/mixed"),
        project_type=ProjectType.NODE,
        marker_files=["package.json"],
        artifacts=[
            ArtifactInfo(
                path=Path("/mixed/a"),
                size_bytes=100,
                last_modified=now,
                artifact_type="cache",
            ),
            ArtifactInfo(
                path=Path("/mixed/b"),
                size_bytes=10_000,
                last_modified=now,
                artifact_type="node_modules",
            ),
        ],
    )

    filter_projects_by_artifact_size([project], 1000)
    assert len(project.artifacts) == 2


def test_parse_size_threshold_units():
    assert parse_size_threshold("100") == 100
    assert parse_size_threshold("1KB") == 1024
    assert parse_size_threshold("1.5MB") == int(1.5 * 1024 * 1024)
    assert parse_size_threshold("2 gb") == 2 * 1024 * 1024 * 1024


def test_parse_size_threshold_invalid():
    with pytest.raises(ValueError):
        parse_size_threshold("wat")


def test_format_size_units():
    assert format_size(0) == "0.00 B"
    assert format_size(1023) == "1023.00 B"
    assert format_size(1024) == "1.00 KB"
    assert format_size(1024 * 1024) == "1.00 MB"


def test_format_size_negative_raises():
    with pytest.raises(ValueError):
        format_size(-1)


def test_is_ignored_path_known_dirs():
    root = Path("/workspace")
    assert is_ignored_path(root / ".git") is True
    assert is_ignored_path(root / ".idea") is True
    assert is_ignored_path(root / "src") is False


def test_is_ignored_path_custom():
    assert is_ignored_path(Path("dist"), custom_ignores={"dist"}) is True
