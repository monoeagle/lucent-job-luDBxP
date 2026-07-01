"""Einmal-Helfer (NICHT Teil des Builds): liest projekt-roadmap-1.mmd (Datum+Status)
und entwicklung-arbeitspakete-1.mmd (Thema je AP via subgraph) und druckt APS-Kandidaten.
Ergebnis manuell in roadmap_data.py kuratieren."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "mermaid-sources"

# 1) Datum + Status + Label aus dem Gantt
gantt = (SRC / "projekt-roadmap-1.mmd").read_text(encoding="utf-8")
# Zeilenform:  AP-11 — Composite FK … :done, b2, 2026-06-26, 1d
row = re.compile(r"^\s*(AP-\d+[^:]*?)\s*:(done|active|crit|)?[^,]*,\s*\w+,\s*(\d{4}-\d{2}-\d{2})", re.M)
gantt_rows = [(m.group(1).strip(), m.group(3), "done" if ":done" in m.group(0) else "open")
              for m in row.finditer(gantt)]

# 2) Thema je AP aus dem Flowchart (subgraph-Zuordnung)
flow = (SRC / "entwicklung-arbeitspakete-1.mmd").read_text(encoding="utf-8")
theme_of: dict[str, str] = {}
cur = None
CMAP = {  # subgraph-Id → THEMES-key (siehe roadmap_data.THEMES)
    "C1": "engine", "C2": "backends", "C3": "sqlbuilder", "C4": "graphviz",
    "C5": "datenui", "C6": "betrieb", "C7": "doku", "C8": "migration",
    "C9": "objekte", "C10": "verbux",
}
for line in flow.splitlines():
    sg = re.search(r"subgraph (C\d+)\[", line)
    if sg:
        cur = CMAP.get(sg.group(1))
    for ap in re.findall(r"AP-\d+", line):
        if cur:
            theme_of.setdefault(ap, cur)

for label, d, status in gantt_rows:
    ap = re.match(r"AP-\d+", label).group(0)
    theme = theme_of.get(ap, "?TODO?")
    print(f'    {{"ap": "{ap}", "label": "…", "theme": "{theme}", "date": "{d}", "status": "{status}"}},')
