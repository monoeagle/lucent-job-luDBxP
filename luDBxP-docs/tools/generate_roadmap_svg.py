"""AP-68 — Roadmap-Swimlane-Generator.

Erzeugt aus roadmap_data.py (Single Source of Truth) einen SVG mit konstanter
Höhe: eine Lane je Themenbereich, erledigte Historie als ein verdichteter Balken,
offene APs als benannte Rauten an ihrem Zieldatum. Stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class Lane:
    key: str
    label: str
    done_span: tuple[date, date] | None
    markers: list[tuple[str, str, date]] = field(default_factory=list)


def validate(aps: list[dict], themes: list[tuple[str, str]]) -> None:
    if not aps:
        raise ValueError("APS ist leer")
    keys = {k for k, _ in themes}
    for a in aps:
        if a["theme"] not in keys:
            raise ValueError(f"unbekanntes theme {a['theme']!r} ({a['ap']})")
        if a["status"] not in ("done", "open"):
            raise ValueError(f"ungültiger status {a['status']!r} ({a['ap']})")
        parse_date(a["date"])  # wirft ValueError bei kaputtem Datum


def lane_spans(aps: list[dict], themes: list[tuple[str, str]]) -> list[Lane]:
    validate(aps, themes)
    lanes: list[Lane] = []
    for key, label in themes:
        mine = [a for a in aps if a["theme"] == key]
        done = [parse_date(a["date"]) for a in mine if a["status"] == "done"]
        span = (min(done), max(done)) if done else None
        markers = sorted(
            ((a["ap"], a["label"], parse_date(a["date"])) for a in mine if a["status"] == "open"),
            key=lambda m: m[2],
        )
        lanes.append(Lane(key, label, span, markers))
    return lanes
