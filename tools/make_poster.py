#!/usr/bin/env python3
"""KANONISCHE Vorlage — A0-Projektposter-Generator (Pillow, kein externer Dienst).

Quelle der Wahrheit für `<project>/tools/make_poster.py`. Siehe
`.pattern/project-poster.pattern` für den Gesamt-Workflow (ADB-Screenshots, Diagramme
via mmdc→PNG, Build). Beim Einsatz in ein Projekt kopieren und NUR den PROJEKT-KONFIG-Block
unten anpassen. Etabliert in lucent-app-snoocount + lucent-app-libreDrive.

Layout: Titel oben · Screenshot-Raster (auto-skaliert, Index-Badges) · Diagramme ·
unten zwei gerahmte Boxen mit gleicher Ober-/Unterkante: links Insights (KANON:
gefülltes Kachel-Raster — Commits/aktive Tage/Streak/Tests + je Commit-Art eine
Kachel, aus project-activity.json), rechts Schriftfeld.

Eingaben (alle in <ROOT>/mail/):
  - Screenshots:  Screenshot_*luDBxP.jpg  (per Playwright; siehe project-poster.pattern A)
  - Diagramm 1:   diagramm-ap-ueberblick.jpg     (AP-Überblick, via mmdc aus .mmd)
  - Diagramm 2:   diagramm-gantt-zeitleiste.jpg  (Gantt, via mmdc aus .mmd)
"""
import glob
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  PROJEKT-KONFIG — beim Einsatz in ein Projekt NUR diesen Block anpassen.   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
ROOT          = "/home/meagle/Dokumente/_Projects/lucent-job-luDBxP"
DISPLAY_NAME  = "Lucent DB Explorer"               # Titel + Schriftfeld-Kopf
SUBTITLE_BASE = "FK-Graph · Join-Pfad-Builder · read-only SQL · Python/Flask"  # vor „ vX.Y.Z · … · Stand …"
APP_VERSION   = "0.3.1"                            # bei jedem Bump anpassen
POSTER_DATE   = "2026-06-26"
AUTHOR        = "Tobias Philipp"
GITHUB        = "github.com/monoeagle"
SCREENSHOT_GLOB = "Screenshot_*luDBxP.jpg"         # Querformat-Browser-Screenshots
# Pfad zum Doku-Aktivitäts-JSON (für Insights-Block); relativ zu ROOT:
ACTIVITY_JSON = "luDBxP-docs/docs/_data/project-activity.json"
OUTPUT_BASENAME = "LucentDBExplorer-Projektposter-A0"
SUBTITLE = f"{SUBTITLE_BASE} v{APP_VERSION} · App-Screens & Arbeitspakete · Stand {POSTER_DATE}"
# ── Ende Konfig ──────────────────────────────────────────────────────────────

MAIL = os.path.join(ROOT, "mail")

# --- A0 hochkant @ 150 dpi ---
DPI = 150
W, H = 4967, 7022
MARGIN = 120
FRAME = 46
GAP = 44
COLS = 4  # Querformat-Browser-Screenshots: 4 Spalten (1400x900 Viewport)

# Browser-App (kein Android): keine System-Leisten zu croppen
CROP_TOP = 0
CROP_BOTTOM = 0

INK = (24, 26, 34)
GRAY = (110, 116, 130)
LINE = (60, 64, 78)
SWATCH = {"done": (31, 111, 60), "wip": (122, 92, 0), "plan": (44, 53, 80)}

FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
def f(path, size): return ImageFont.truetype(path, size)

# Insights-Kennzahlen aus dem Doku-Aktivitäts-JSON (wie auf der Doku-Startseite).
PILL_BG = {
    "feat": (216, 240, 222), "fix": (244, 219, 219), "docs": (214, 240, 232),
    "refactor": (245, 232, 206), "chore": (228, 228, 232), "build": (228, 228, 232),
    "other": (228, 228, 232), "perf": (255, 231, 204),
}

def load_stats():
    """stats-Block aus dem Doku-Aktivitäts-JSON (oder None)."""
    p = os.path.join(ROOT, ACTIVITY_JSON)
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh).get("stats")
    except OSError:
        return None

canvas = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(canvas)

# Rahmen (technische Zeichnung)
d.rectangle([FRAME, FRAME, W - FRAME, H - FRAME], outline=LINE, width=4)
d.rectangle([FRAME + 10, FRAME + 10, W - FRAME - 10, H - FRAME - 10], outline=(180, 184, 196), width=2)

cx0, cx1 = MARGIN, W - MARGIN
content_w = cx1 - cx0

# --- Ueberschrift ---
title_font = f(FB, 132)
sub_font = f(FR, 54)
y = MARGIN + 6
d.text((cx0, y), f"{DISPLAY_NAME} — Projektposter", font=title_font, fill=INK)
y += 150
d.text((cx0, y), SUBTITLE, font=sub_font, fill=GRAY)
y += 78
d.line([cx0, y, cx1, y], fill=LINE, width=3)
heading_bottom = y + 8

def load_shot(path):
    """Screenshot laden + Android-System-Leisten oben/unten abschneiden."""
    im = Image.open(path)
    w, h = im.size
    top = min(CROP_TOP, h)
    bot = max(top + 1, h - CROP_BOTTOM)
    return im.crop((0, top, w, bot))

def fit(img, bw, bh):
    iw, ih = img.size
    s = min(bw / iw, bh / ih)
    return img.resize((max(1, int(iw * s)), max(1, int(ih * s))), Image.LANCZOS)

def paste_framed(img, bx, by, bw, bh):
    im = fit(img, bw, bh)
    px = bx + (bw - im.width) // 2
    py = by + (bh - im.height) // 2
    canvas.paste(im, (px, py))
    d.rectangle([px - 2, py - 2, px + im.width + 1, py + im.height + 1], outline=(150, 154, 166), width=2)
    return px, py, im.width, im.height

# --- Bilder einsammeln ---
shots = sorted(glob.glob(os.path.join(MAIL, SCREENSHOT_GLOB)))
diagrams = [
    (os.path.join(MAIL, "diagramm-architektur.jpg"), "Systemüberblick · UI → Flask-API → Core-Layer"),
    (os.path.join(MAIL, "diagramm-ap-ueberblick.jpg"), "Arbeitspakete im Überblick · 3 Phasen (Fundament · UI/Daten · Features)"),
]
diagrams = [(p, c) for p, c in diagrams if os.path.exists(p)]

# --- Titelblock (Schriftfeld) unten rechts — Koordinaten vorab fuer Layout-Baender ---
tb_w, tb_h = 2180, 660
tb_x1, tb_y1 = cx1, H - MARGIN
tb_x0, tb_y0 = tb_x1 - tb_w, tb_y1 - tb_h

# --- Diagramme OBEN: Architektur (volle Breite) + AP-Band darunter ---
cap_h = 60
DIAG_GAP = 70
cap_font = f(FB, 46)
loaded = [(Image.open(p), cap) for p, cap in diagrams]
diag_top = heading_bottom + 54
diag_bottom = diag_top
if loaded:
    # Volle Inhaltsbreite; nur skalieren, falls die Bänder zu hoch würden, damit
    # das Screenshot-Raster darunter Platz behält (max. ~62% der Restfläche).
    diag_natural = sum(cap_h + int(content_w * im.size[1] / im.size[0]) for im, _ in loaded) + 60 * len(loaded)
    diag_band_max = int((tb_y0 - diag_top) * 0.62)
    scale = min(1.0, diag_band_max / diag_natural) if diag_natural > 0 else 1.0
    dw = int(content_w * scale)
    dx = cx0 + (content_w - dw) // 2
    dy = diag_top
    for im, cap in loaded:
        d.text((dx, dy), cap, font=cap_font, fill=INK)
        dyc = dy + cap_h
        dh = int(dw * im.size[1] / im.size[0])
        paste_framed(im, dx, dyc, dw, dh)
        dy = dyc + dh + 60
    diag_bottom = dy

# --- Screenshot-Raster DARUNTER (4-spaltig, füllt bis zum Titelblock) ---
grid_top = diag_bottom + DIAG_GAP
grid_band_h = tb_y0 - DIAG_GAP - grid_top
grid_bottom = grid_top
if shots:
    col_w = (content_w - (COLS - 1) * GAP) // COLS
    sample = load_shot(shots[0]); asp = sample.size[0] / sample.size[1]
    cell_h = col_w / asp
    n = len(shots)
    rows = math.ceil(n / COLS)
    natural_h = rows * cell_h + (rows - 1) * GAP
    gscale = min(1.0, grid_band_h / natural_h) if natural_h > 0 else 1.0
    col_w = int(col_w * gscale)
    cell_h = int(cell_h * gscale)
    idx_font = f(FB, max(22, int(40 * gscale)))
    for i, p in enumerate(shots):
        r, c = divmod(i, COLS)
        items_in_row = COLS if (r < rows - 1 or n % COLS == 0) else n % COLS
        row_w = items_in_row * col_w + (items_in_row - 1) * GAP
        row_x0 = cx0 + (content_w - row_w) // 2
        bx = row_x0 + c * (col_w + GAP)
        by = grid_top + r * (cell_h + GAP)
        px, py, iw, ih = paste_framed(load_shot(p), bx, by, col_w, cell_h)
        # Index-Badge (Startscreen = 01)
        badge = f"{i + 1:02d}"
        bb = idx_font.getbbox(badge)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.rectangle([px, py, px + tw + 18, py + th + 16], fill=(24, 26, 34))
        d.text((px + 9, py + 4), badge, font=idx_font, fill="white")
    grid_bottom = grid_top + rows * cell_h + (rows - 1) * GAP

# (Diagramme werden jetzt OBEN gezeichnet — siehe Block vor dem Screenshot-Raster)

# --- Insights (KACHEL-RASTER: jede Kennzahl eine eigene Kachel) unten links ---
# KANON: Insights IMMER als gefülltes Kachel-Raster — Headline-Kennzahlen
# (Commits / aktive Tage / längster Streak / Tests) + je Commit-Art eine Kachel.
ins_x0 = cx0
ins_x1 = tb_x0 - 60          # 60 px Luft zum Schriftfeld
PAD = 32
d.rectangle([ins_x0, tb_y0, ins_x1, tb_y1], fill="white", outline=INK, width=4)

bx0 = ins_x0 + PAD
bx1 = ins_x1 - PAD
bw = bx1 - bx0
by = tb_y0 + PAD
stats = load_stats()

# Akzentfarbe (linke Kante) je Commit-Art
KIND_ACCENT = {
    "feat": (46, 160, 86), "fix": (214, 90, 90), "docs": (70, 150, 180),
    "refactor": (210, 160, 40), "chore": (130, 130, 150), "build": (120, 120, 140),
    "other": (150, 150, 162), "perf": (220, 140, 60), "test": (120, 100, 180),
}
if stats:
    d.text((bx0, by), "Insights", font=f(FB, 50), fill=INK)
    by += 78
    tiles = [
        (str(stats.get("totalCommits", "–")), "COMMITS", SWATCH["done"]),
        (str(stats.get("activeDays", "–")), "AKTIVE TAGE", SWATCH["done"]),
        (str(stats.get("longestStreak", "–")), "LÄNGSTER STREAK", SWATCH["done"]),
        (str(stats.get("testCount", "–")), "TESTS", SWATCH["done"]),
    ]
    # Jede Commit-Art bekommt eine eigene Kachel (statt kleiner Pills)
    for k in stats.get("topKinds", []):
        tiles.append((str(k["count"]), k["kind"].upper(),
                      KIND_ACCENT.get(k["kind"], (140, 140, 152))))
    cols = 4
    rows = math.ceil(len(tiles) / cols)
    tg = 18
    tile_w = (bw - (cols - 1) * tg) // cols
    tile_h = (tb_y1 - PAD - by - (rows - 1) * tg) // rows
    numf, labf = f(FB, 70), f(FR, 26)
    for i, (num, lab, acc) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = bx0 + c * (tile_w + tg)
        yy = by + r * (tile_h + tg)
        d.rectangle([x, yy, x + tile_w, yy + tile_h], fill=(240, 243, 247), outline=(150, 154, 166), width=2)
        d.rectangle([x, yy, x + 9, yy + tile_h], fill=acc)        # Akzent-Kante links
        d.text((x + 26, yy + 18), num, font=numf, fill=INK)
        d.text((x + 28, yy + tile_h - 42), lab, font=labf, fill=GRAY)

# Titelblock zeichnen
d.rectangle([tb_x0, tb_y0, tb_x1, tb_y1], fill="white", outline=INK, width=4)
hdr_h = 118
d.rectangle([tb_x0, tb_y0, tb_x1, tb_y0 + hdr_h], fill=(24, 26, 34))
d.text((tb_x0 + 28, tb_y0 + 24), DISPLAY_NAME, font=f(FB, 64), fill="white")
d.text((tb_x1 - 360, tb_y0 + 40), "Projektposter", font=f(FR, 40), fill=(200, 204, 216))
rows_tb = [
    ("Ersteller", AUTHOR),
    ("GitHub", GITHUB),
    ("Datum", POSTER_DATE),
    ("Version", APP_VERSION),
    ("Format", "A0 · 841 × 1189 mm"),
    ("Inhalt", f"{len(shots)} Screens + {len(diagrams)} Diagramme"),
]
row_h = (tb_h - hdr_h) // len(rows_tb)
lab_w = 560
lf2 = f(FR, 38)
vf2 = f(FM, 42)
ry = tb_y0 + hdr_h
for lab, val in rows_tb:
    d.line([tb_x0, ry, tb_x1, ry], fill=(170, 174, 186), width=2)
    d.line([tb_x0 + lab_w, ry, tb_x0 + lab_w, ry + row_h], fill=(170, 174, 186), width=2)
    d.text((tb_x0 + 24, ry + row_h // 2 - 24), lab, font=lf2, fill=GRAY)
    d.text((tb_x0 + lab_w + 28, ry + row_h // 2 - 26), val, font=vf2, fill=INK)
    ry += row_h

out = os.path.join(MAIL, f"{OUTPUT_BASENAME}.jpg")
canvas.save(out, "JPEG", quality=88, dpi=(DPI, DPI))
out_pdf = os.path.join(MAIL, f"{OUTPUT_BASENAME}.pdf")
canvas.save(out_pdf, "PDF", resolution=DPI)
print("OK", out, f"{W}x{H}", f"{os.path.getsize(out)//1024} KB")
print("OK", out_pdf, f"{os.path.getsize(out_pdf)//1024} KB")
