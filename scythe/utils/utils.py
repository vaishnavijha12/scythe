"""
    Utils functions
"""

import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from scythe.models.models import Project

IGNORED_PATTERNS: Set[str] = {
    '.git',
    '.svn',
    '.hg',
    '.bzr',
    '__MACOSX',
    '.DS_Store',
    'Thumbs.db',
    '.idea',
    '.vscode',
    '*.swp',
    '*.swo',
    '*~'
}


SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024 ** 2,
    "GB": 1024 ** 3,
    "TB": 1024 ** 4,
}


def format_size(size_bytes: int) -> str:
    if size_bytes < 0 :
        raise ValueError("Size must be positive")

    for unit in ['B','KB','MB','GB', 'TB']:
        if size_bytes < 1024.0 :
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def calculate_directory_size(path: Path, follow_symlinks: bool = False) -> int:
    if not path.exists():
        raise ValueError("The path does not exist")
    if not path.is_dir():
        raise ValueError("Path is not a directory")

    total_size = 0

    try:
        for entry in path.rglob('*'):
            if entry.is_symlink() and not follow_symlinks:
                continue
            if entry.is_file():
                try:
                    total_size+= entry.stat().st_size
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass

    return total_size


def parse_size_threshold(value: str | None) -> int | None:
    """
    Parse a user-supplied size like ``100MB`` or ``1.5GB`` into bytes.
    Returns ``None`` when the option is unset.
    """
    if value is None:
        return None

    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([kmgt]?b)?\s*", value, re.IGNORECASE)
    if not match:
        raise ValueError(
            "Invalid size. Use raw bytes or a unit like 100MB, 1GB, or 512KB."
        )

    amount = float(match.group(1))
    unit = (match.group(2) or "B").upper()
    size_bytes = int(amount * SIZE_UNITS[unit])

    if size_bytes < 0:
        raise ValueError("Size must be positive")

    return size_bytes


def filter_projects_by_artifact_age(
    projects: List["Project"],
    min_age_days: int,
    now: datetime | None = None,
) -> List["Project"]:
    """
    Return a new list of Projects whose artifacts are at least
    `min_age_days` old (based on `last_modified`). Projects whose every
    artifact is too recent are dropped entirely.

    `now` is injectable to make tests deterministic.
    """
    if min_age_days <= 0:
        return list(projects)

    from scythe.models.models import Project

    reference = now or datetime.now()
    cutoff = reference - timedelta(days=min_age_days)
    result: List[Project] = []
    for project in projects:
        old_artifacts = [a for a in project.artifacts if a.last_modified <= cutoff]
        if not old_artifacts:
            continue
        result.append(
            Project(
                path=project.path,
                project_type=project.project_type,
                marker_files=list(project.marker_files),
                artifacts=old_artifacts,
                last_scanned=project.last_scanned,
            )
        )
    return result


def filter_projects_by_artifact_size(
    projects: List["Project"],
    min_size_bytes: int,
) -> List["Project"]:
    """
    Return a new list of Projects whose artifacts are at least
    ``min_size_bytes`` large. Projects whose every artifact is too small
    are dropped entirely.
    """
    if min_size_bytes <= 0:
        return list(projects)

    from scythe.models.models import Project

    result: List[Project] = []
    for project in projects:
        large_artifacts = [a for a in project.artifacts if a.size_bytes >= min_size_bytes]
        if not large_artifacts:
            continue
        result.append(
            Project(
                path=project.path,
                project_type=project.project_type,
                marker_files=list(project.marker_files),
                artifacts=large_artifacts,
                last_scanned=project.last_scanned,
            )
        )
    return result


def is_ignored_path(path: Path, custom_ignores: Set[str] = None) -> bool :
    ignored = IGNORED_PATTERNS.copy()
    if custom_ignores:
        ignored.update(custom_ignores)

    if path.name in ignored:
        return True

    for pattern in ignored:
        if '*' in pattern :
            pattern_clean = pattern.replace('*', '')
            if pattern_clean in path.name :
                return True
    return False
