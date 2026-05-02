"""
Demo fixture helper for the VHS recording.

Avoids depending on bash / dd / du so the tape runs the same on Windows
(PowerShell), macOS, and Linux. Used exclusively by demo/demo.tape.

Usage:
    python demo/fixture.py setup     # build a fake project tree under TEMP
    python demo/fixture.py size      # print total size of the demo tree
    python demo/fixture.py cleanup   # remove the demo tree
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(tempfile.gettempdir()) / "scythe-demo"

# (relative dir, marker filename, marker contents, fake-artifact dir, fake-artifact file size)
LAYOUT = [
    ("webapp",  "package.json",   "{}",            "node_modules", 80 * 1024 * 1024),
    ("api",     "pyproject.toml", "[project]\n",   ".venv",        25 * 1024 * 1024),
    ("service", "Cargo.toml",     "[package]\n",   "target",       120 * 1024 * 1024),
]


def _write_blob(path: Path, size: int) -> None:
    """Create a file of `size` bytes without holding it all in memory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    chunk = b"\0" * (1024 * 1024)
    remaining = size
    with path.open("wb") as f:
        while remaining > 0:
            f.write(chunk if remaining >= len(chunk) else b"\0" * remaining)
            remaining -= len(chunk)


def setup() -> None:
    cleanup()
    for project_dir, marker, marker_body, artifact_dir, artifact_size in LAYOUT:
        project = ROOT / project_dir
        project.mkdir(parents=True, exist_ok=True)
        (project / marker).write_text(marker_body, encoding="utf-8")
        _write_blob(project / artifact_dir / "blob.bin", artifact_size)


def total_size() -> int:
    if not ROOT.exists():
        return 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        for name in filenames:
            try:
                total += (Path(dirpath) / name).stat().st_size
            except OSError:
                pass
    return total


def _format(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def cleanup() -> None:
    shutil.rmtree(ROOT, ignore_errors=True)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"setup", "size", "cleanup", "path"}:
        print(__doc__, file=sys.stderr)
        return 2

    cmd = argv[1]
    if cmd == "setup":
        setup()
        print(f"Demo tree ready at {ROOT}")
    elif cmd == "size":
        print(f"Total disk usage: {_format(total_size())}")
    elif cmd == "cleanup":
        cleanup()
    elif cmd == "path":
        print(ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
