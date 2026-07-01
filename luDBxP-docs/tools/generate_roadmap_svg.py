"""AP-68 — Roadmap-Swimlane-Generator.

Erzeugt aus roadmap_data.py (Single Source of Truth) einen SVG mit konstanter
Höhe: eine Lane je Themenbereich, erledigte Historie als ein verdichteter Balken,
offene APs als benannte Rauten an ihrem Zieldatum. Stdlib-only.
"""
from __future__ import annotations

from datetime import date


def parse_date(s: str) -> date:
    return date.fromisoformat(s)


def date_range(aps: list[dict]) -> tuple[date, date]:
    ds = [parse_date(a["date"]) for a in aps]
    return min(ds), max(ds)


def date_to_x(d: date, dmin: date, dmax: date, x0: float, x1: float) -> float:
    span = (dmax - dmin).days
    if span == 0:
        return x0
    frac = (d - dmin).days / span
    return x0 + frac * (x1 - x0)
