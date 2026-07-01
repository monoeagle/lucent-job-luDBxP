import sys
from datetime import date
from pathlib import Path

import pytest

# Generator liegt in der Doku-Toolchain; stdlib-only → unter dem Projekt-venv importierbar.
_TOOLS = Path(__file__).resolve().parent.parent / "luDBxP-docs" / "tools"
sys.path.insert(0, str(_TOOLS))

import generate_roadmap_svg as g  # noqa: E402


def test_parse_date():
    assert g.parse_date("2026-06-25") == date(2026, 6, 25)


def test_date_range():
    aps = [
        {"date": "2026-06-25"},
        {"date": "2026-07-12"},
        {"date": "2026-06-28"},
    ]
    assert g.date_range(aps) == (date(2026, 6, 25), date(2026, 7, 12))


def test_date_to_x_endpoints_and_midpoint():
    dmin, dmax = date(2026, 6, 25), date(2026, 7, 5)  # 10 Tage
    assert g.date_to_x(dmin, dmin, dmax, 100.0, 1100.0) == 100.0
    assert g.date_to_x(dmax, dmin, dmax, 100.0, 1100.0) == 1100.0
    # Tag 5 von 10 → Mitte
    assert g.date_to_x(date(2026, 6, 30), dmin, dmax, 100.0, 1100.0) == 600.0


def test_date_to_x_collapsed_range():
    d = date(2026, 6, 25)
    assert g.date_to_x(d, d, d, 100.0, 1100.0) == 100.0


_THEMES = [("engine", "⚙️ Engine"), ("betrieb", "🚀 Betrieb")]


def _aps():
    return [
        {"ap": "AP-1", "label": "A", "theme": "engine", "date": "2026-06-25", "status": "done"},
        {"ap": "AP-2", "label": "B", "theme": "engine", "date": "2026-06-28", "status": "done"},
        {"ap": "AP-31", "label": "Idle", "theme": "betrieb", "date": "2026-07-05", "status": "open"},
        {"ap": "AP-35", "label": "venv", "theme": "betrieb", "date": "2026-07-02", "status": "open"},
    ]


def test_lane_spans_done_and_markers():
    lanes = g.lane_spans(_aps(), _THEMES)
    assert [l.key for l in lanes] == ["engine", "betrieb"]
    engine = lanes[0]
    assert engine.done_span == (date(2026, 6, 25), date(2026, 6, 28))
    assert engine.markers == []
    betrieb = lanes[1]
    assert betrieb.done_span is None
    # nach Datum sortiert: AP-35 (07-02) vor AP-31 (07-05)
    assert [m[0] for m in betrieb.markers] == ["AP-35", "AP-31"]


def test_validate_rejects_unknown_theme():
    bad = [{"ap": "AP-9", "label": "x", "theme": "nope", "date": "2026-06-25", "status": "done"}]
    with pytest.raises(ValueError, match="theme"):
        g.validate(bad, _THEMES)


def test_validate_rejects_empty():
    with pytest.raises(ValueError, match="leer"):
        g.validate([], _THEMES)


def test_validate_rejects_bad_status():
    bad = [{"ap": "AP-9", "label": "x", "theme": "engine", "date": "2026-06-25", "status": "wip"}]
    with pytest.raises(ValueError, match="status"):
        g.validate(bad, _THEMES)


def test_render_svg_wellformed_and_contains_open_labels():
    lanes = g.lane_spans(_aps(), _THEMES)
    dmin, dmax = g.date_range(_aps())
    svg = g.render_svg(lanes, dmin, dmax)
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # Enumerate-Regel: jede offene AP muss namentlich im SVG stehen
    assert "AP-31" in svg and "AP-35" in svg
    # intrinsische Pixel-Breite, nicht width="100%"
    assert 'width="1200"' in svg
    assert 'width="100%"' not in svg
    # Done-Farbe der erledigten Lane vorhanden
    assert "#1f6f3c" in svg


def test_esc():
    assert g.esc("A & B <x>") == "A &amp; B &lt;x&gt;"
