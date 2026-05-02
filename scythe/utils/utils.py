"""
    Utils functions
"""

import os
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