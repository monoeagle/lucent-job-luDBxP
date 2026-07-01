import sys
from datetime import date
from pathlib import Path

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
