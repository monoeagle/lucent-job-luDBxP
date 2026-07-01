"""AP-68 — Roadmap-Swimlane-Generator.

Erzeugt aus roadmap_data.py (Single Source of Truth) einen SVG mit konstanter
Höhe: eine Lane je Themenbereich, erledigte Historie als ein verdichteter Balken
(mit Anzahl erledigter APs), offene/in-Arbeit-APs als 🚧-Marker an ihrem
Zieldatum. Stdlib-only.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path


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
    done_count: int = 0


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
        lanes.append(Lane(key, label, span, markers, done_count=len(done)))
    return lanes


MARGIN_LEFT = 210
MARGIN_TOP = 70
LANE_H = 40
LEGEND_H = 44
PLOT_PAD_RIGHT = 30

DONE_FILL = "#1f6f3c"
OPEN_FILL = "#234a78"
LANE_BG_A = "#f7f7fa"
LANE_BG_B = "#ffffff"
AXIS_COL = "#9aa0a6"
LABEL_COL = "#33373b"

# Emoji-Marker für offene/in-Arbeit-APs (rendert wie die Lane-Emojis in Chrome).
WIP_ICON = "\U0001f6a7"  # 🚧
_CHAR_W = 5.4            # grobe Zeichenbreite bei font-size 10 (Label-Kollisionsschätzung)
_LABEL_LEVELS = (4, -9, 17)  # vertikale Versatz-Ebenen relativ zur Lane-Mitte


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _axis_ticks(dmin: date, dmax: date, step_days: int = 3) -> list[date]:
    ticks, d = [], dmin
    while d <= dmax:
        ticks.append(d)
        d += timedelta(days=step_days)
    if ticks[-1] != dmax:
        ticks.append(dmax)
    return ticks


def render_svg(lanes: list[Lane], dmin: date, dmax: date, *, width: int = 1200) -> str:
    x0, x1 = MARGIN_LEFT, width - PLOT_PAD_RIGHT
    height = MARGIN_TOP + len(lanes) * LANE_H + LEGEND_H
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    )
    parts.append(f'<rect width="{width}" height="{height}" fill="#ffffff"/>')
    parts.append(
        f'<text x="{width / 2:.0f}" y="30" font-size="20" font-weight="700" '
        f'text-anchor="middle" fill="{LABEL_COL}">'
        f'LucentTools DB Explorer — Arbeitspaket-Roadmap</text>'
    )

    # X-Achse (Datums-Ticks) über die volle Plot-Höhe
    plot_bottom = MARGIN_TOP + len(lanes) * LANE_H
    for t in _axis_ticks(dmin, dmax):
        x = date_to_x(t, dmin, dmax, x0, x1)
        parts.append(
            f'<line x1="{x:.1f}" y1="{MARGIN_TOP}" x2="{x:.1f}" y2="{plot_bottom}" '
            f'stroke="{AXIS_COL}" stroke-width="0.5" stroke-dasharray="2 3"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{MARGIN_TOP - 6}" font-size="10" text-anchor="middle" '
            f'fill="{AXIS_COL}">{t.strftime("%d.%m")}</text>'
        )

    # Lanes
    for i, lane in enumerate(lanes):
        ly = MARGIN_TOP + i * LANE_H
        cy = ly + LANE_H / 2
        bg = LANE_BG_A if i % 2 == 0 else LANE_BG_B
        parts.append(f'<rect x="0" y="{ly}" width="{width}" height="{LANE_H}" fill="{bg}"/>')
        parts.append(
            f'<text x="{MARGIN_LEFT - 12}" y="{cy + 4:.0f}" font-size="12" '
            f'text-anchor="end" fill="{LABEL_COL}">{esc(lane.label)}</text>'
        )
        # Done-Balken + Anzahl erledigter APs
        if lane.done_span:
            s, e = lane.done_span
            bx0 = date_to_x(s, dmin, dmax, x0, x1)
            bx1 = date_to_x(e, dmin, dmax, x0, x1)
            bw = max(6.0, bx1 - bx0)
            parts.append(
                f'<rect x="{bx0:.1f}" y="{ly + 9}" width="{bw:.1f}" height="{LANE_H - 18}" '
                f'rx="3" fill="{DONE_FILL}"/>'
            )
            if lane.done_count:
                if bw >= 22:  # Zahl mittig in den Balken (weiß)
                    parts.append(
                        f'<text x="{bx0 + bw/2:.1f}" y="{cy + 4:.1f}" font-size="12" '
                        f'font-weight="700" text-anchor="middle" fill="#ffffff">'
                        f'{lane.done_count}</text>'
                    )
                else:         # zu schmal → Zahl rechts daneben
                    parts.append(
                        f'<text x="{bx1 + 5:.1f}" y="{cy + 4:.1f}" font-size="11" '
                        f'font-weight="700" fill="{DONE_FILL}">{lane.done_count}</text>'
                    )
        # Offene / in Arbeit: 🚧-Marker + Label, mehrstufiger Anti-Overlap-Versatz.
        # Icon und Label wandern gemeinsam auf die Versatz-Ebene (so überlagert ein
        # Icon nie den Text eines anderen, dicht benachbarten Markers).
        placed: list[tuple[float, float, int]] = []  # (x_start, x_end, level)
        for (ap, label, d) in lane.markers:
            mx = date_to_x(d, dmin, dmax, x0, x1)
            txt = f"{ap} {label}"
            tw = len(txt) * _CHAR_W
            # Nahe dem rechten Rand: Label nach links rendern statt es abzuschneiden.
            if mx + 16 + tw > x1:
                anchor, tx = "end", mx - 12
                xs, xe = tx - tw, mx + 8
            else:
                anchor, tx = "start", mx + 12
                xs, xe = mx - 8, tx + tw
            # Niedrigste Versatz-Ebene ohne Überlappung (Belegung deckt Icon + Label).
            level = len(_LABEL_LEVELS) - 1
            for lvl in range(len(_LABEL_LEVELS)):
                if not any(p[2] == lvl and not (xe < p[0] - 4 or xs > p[1] + 4) for p in placed):
                    level = lvl
                    break
            ty = cy + _LABEL_LEVELS[level]
            parts.append(
                f'<text x="{mx:.1f}" y="{ty:.1f}" font-size="13" '
                f'text-anchor="middle">{WIP_ICON}</text>'
            )
            parts.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="10" text-anchor="{anchor}" '
                f'paint-order="stroke" stroke="#ffffff" stroke-width="2.5" '
                f'stroke-linejoin="round" fill="{OPEN_FILL}">{esc(txt)}</text>'
            )
            placed.append((xs, xe, level))

    # Legende
    lgy = plot_bottom + 22
    parts.append(f'<rect x="{MARGIN_LEFT}" y="{lgy-9}" width="22" height="12" rx="3" fill="{DONE_FILL}"/>')
    parts.append(
        f'<text x="{MARGIN_LEFT+28}" y="{lgy+1}" font-size="11" fill="{LABEL_COL}">'
        f'erledigt (Zeitraum · Zahl = Anzahl APs)</text>'
    )
    dx = MARGIN_LEFT + 290
    parts.append(f'<text x="{dx:.0f}" y="{lgy+4:.0f}" font-size="14" text-anchor="middle">{WIP_ICON}</text>')
    parts.append(f'<text x="{dx+12}" y="{lgy+1}" font-size="11" fill="{LABEL_COL}">in Arbeit / geplant</text>')

    parts.append("</svg>")
    return "\n".join(parts)


OUT = Path(__file__).resolve().parent.parent / "docs" / "images" / "roadmap" / "projekt-roadmap.svg"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import roadmap_data as data
    lanes = lane_spans(data.APS, data.THEMES)
    dmin, dmax = date_range(data.APS)
    svg = render_svg(lanes, dmin, dmax)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"✓ Roadmap-SVG → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
