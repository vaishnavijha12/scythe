"""
Trash-mode primitives for scythe.

Instead of permanently unlinking artifacts, ``--trash`` mode moves them to a
scythe-managed trash directory and writes a per-run manifest so the run
can be undone later via ``scythe restore``.

On-disk layout under ``get_trash_root()``::

    trash/<run_id>/<index>_<basename>   # the moved artifacts (file or dir)
    runs/<run_id>.json                  # the manifest

The manifest records every item's original path, the trash path it was
moved to, its size, and metadata, so a restore is a deterministic
``shutil.move`` per entry.
"""

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def get_trash_root() -> Path:
    """
    Return the per-user data directory where scythe stores trashed
    artifacts and run manifests.

    Honors the standard platform conventions:

    - Linux / *BSD: ``$XDG_DATA_HOME/scythe`` or ``~/.local/share/scythe``
    - macOS:        ``~/Library/Application Support/scythe``
    - Windows:      ``%LOCALAPPDATA%\\scythe``
    """
    if sys.platform == "win32":
        base_str = os.environ.get("LOCALAPPDATA")
        base = Path(base_str) if base_str else Path.home() / "AppData" / "Local"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "scythe"


def new_run_id(now: Optional[datetime] = None) -> str:
    """Timestamp-based run id; sorts lexicographically by recency."""
    return (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")


@dataclass
class TrashedItem:
    index: int
    original_path: str
    trash_path: str
    size_bytes: int
    artifact_type: str
    project_type: str


@dataclass
class RunManifest:
    run_id: str
    scythe_version: str
    started_at: str
    finished_at: Optional[str] = None
    scan_path: Optional[str] = None
    restored_at: Optional[str] = None
    items: List[TrashedItem] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "scythe_version": self.scythe_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "scan_path": self.scan_path,
            "restored_at": self.restored_at,
            "items": [asdict(item) for item in self.items],
        }

    @property
    def total_size(self) -> int:
        return sum(item.size_bytes for item in self.items)


class TrashMover:
    """
    Move artifacts into a per-run scythe trash directory and persist a
    manifest describing the run.

    The mover is single-use: instantiate once per ``clean`` invocation,
    call :meth:`move` for every artifact, then :meth:`finalize` once at
    the end to write the manifest.
    """

    def __init__(
        self,
        run_id: Optional[str] = None,
        *,
        root: Optional[Path] = None,
    ):
        self.root = root or get_trash_root()
        self.run_id = run_id or new_run_id()
        self.trash_dir = self.root / "trash" / self.run_id
        self.runs_dir = self.root / "runs"
        self._next_index = 0

        from scythe import __version__

        self.manifest = RunManifest(
            run_id=self.run_id,
            scythe_version=__version__,
            started_at=datetime.now().isoformat(timespec="seconds"),
        )

    def move(
        self,
        path: Path,
        *,
        size_bytes: int,
        artifact_type: str = "",
        project_type: str = "",
    ) -> Path:
        """
        Move ``path`` into this run's trash dir and record the move.
        Returns the destination path.
        """
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        index = self._next_index
        self._next_index += 1
        dest = self.trash_dir / f"{index}_{path.name}"
        shutil.move(str(path), str(dest))
        self.manifest.items.append(
            TrashedItem(
                index=index,
                original_path=str(path),
                trash_path=str(dest),
                size_bytes=size_bytes,
                artifact_type=artifact_type,
                project_type=project_type,
            )
        )
        return dest

    def finalize(self, *, scan_path: Optional[Path] = None) -> Path:
        """
        Write the manifest JSON to ``runs/<run_id>.json`` and return
        its path. Safe to call even if no items were moved (produces an
        empty-items manifest, which simplifies CLI plumbing).
        """
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.manifest.finished_at = datetime.now().isoformat(timespec="seconds")
        if scan_path is not None:
            self.manifest.scan_path = str(scan_path)
        manifest_path = self.runs_dir / f"{self.run_id}.json"
        manifest_path.write_text(
            json.dumps(self.manifest.to_dict(), indent=2),
            encoding="utf-8",
        )
        return manifest_path


def list_runs(root: Optional[Path] = None) -> List[Path]:
    """Return manifest paths sorted newest-first."""
    runs_dir = (root or get_trash_root()) / "runs"
    if not runs_dir.exists():
        return []
    return sorted(runs_dir.glob("*.json"), reverse=True)


def load_manifest(manifest_path: Path) -> Dict:
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def restore_run(manifest_path: Path) -> Dict:
    """
    Move every item recorded in ``manifest_path`` back to its original
    location. Returns a summary::

        {
            "restored": [original_path, ...],
            "skipped":  [{"path": ..., "reason": ...}, ...],
            "errors":   [{"path": ..., "error":  ...}, ...],
        }

    An item is skipped (rather than failing) when its trash entry no
    longer exists or when something already lives at the original
    destination — restoring on top of a re-created `node_modules/` would
    almost always be a mistake.
    """
    data = load_manifest(manifest_path)
    summary: Dict[str, list] = {"restored": [], "skipped": [], "errors": []}

    for item in data.get("items", []):
        original = Path(item["original_path"])
        trash = Path(item["trash_path"])

        if not trash.exists():
            summary["skipped"].append(
                {"path": str(original), "reason": "trash entry missing"}
            )
            continue
        if original.exists():
            summary["skipped"].append(
                {"path": str(original), "reason": "destination already exists"}
            )
            continue

        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trash), str(original))
            summary["restored"].append(str(original))
        except (OSError, PermissionError) as exc:
            summary["errors"].append({"path": str(original), "error": str(exc)})

    if summary["restored"] and not summary["errors"]:
        data["restored_at"] = datetime.now().isoformat(timespec="seconds")
        manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return summary
