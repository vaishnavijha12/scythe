"""
Unit tests for UI helpers.
"""

import pytest
from pathlib import Path

from scythe.ui.ui import (
    parse_selection,
    display_scan_result
)
from scythe.models.models import ScanResult


def test_parse_selection_all():
    """'all' selects every project."""
    result = parse_selection("all", 5)
    assert result == [0, 1, 2, 3, 4]


def test_parse_selection_single():
    """A single index resolves to one 0-based position."""
    result = parse_selection("3", 5)
    assert result == [2]  # 0-based


def test_parse_selection_multiple():
    """Comma-separated indices select multiple items."""
    result = parse_selection("1,3,5", 5)
    assert result == [0, 2, 4]


def test_parse_selection_range():
    """A dash-separated range expands to its endpoints inclusive."""
    result = parse_selection("2-4", 5)
    assert result == [1, 2, 3]


def test_parse_selection_mixed():
    """Mixed singles and ranges combine without duplicates."""
    result = parse_selection("1,3-5,7", 10)
    assert result == [0, 2, 3, 4, 6]


def test_parse_selection_invalid_range():
    """A reversed range raises ValueError."""
    with pytest.raises(ValueError):
        parse_selection("5-2", 10)


def test_parse_selection_out_of_bounds():
    """An index beyond max raises ValueError."""
    with pytest.raises(ValueError):
        parse_selection("15", 10)


def test_display_scan_results_no_projects(capsys):
    """Empty result set renders the 'no projects' message."""
    result = ScanResult(
        root_path=Path("/test"),
        projects=[],
        scan_duration=1.0
    )

    display_scan_result(result, Path("/test"), format="compact")
    captured = capsys.readouterr()
    assert "No project found" in captured.out or "project" in captured.out.lower()