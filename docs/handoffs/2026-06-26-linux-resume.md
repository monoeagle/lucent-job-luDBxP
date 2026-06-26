# Resume-Prompt — Linux-Session (LucentTools DB Explorer)

Vorbereitet auf Windows (Session 4, 2026-06-26) für die Weiterarbeit auf dem **Linux-Rechner**.
Bezug: vollständiger Handoff in `docs/handoffs/2026-06-26-1845.md`.

---
## Resume-Prompt (kopieren für die Linux-Session)

Weitermachen mit **LucentTools DB Explorer** (lucent-job-luDBxP) auf dem **Linux-Rechner**.
Letzte Arbeit lief auf Windows (Session 4, 2026-06-26 18:45), Stand **v0.11.3**, **118 Tests grün**, alles nach `origin/master` gepusht (`docs`-Commit mit diesem Resume-Prompt obendrauf).

**ZUERST:** `git fetch` + Divergenz prüfen, dann `git pull`. Working Tree muss sauber/synchron sein. Danach `./venv/bin/python -m pytest` als Baseline (Linux-venv ggf. via `bash run.sh` neu bauen).

**Fokus dieser Session = Linux-Part + offene Linux-APs:**

1. **AP-15 — `run.sh` abbruchsicher + idempotent (Parität zu `run.ps1`)** — *zuerst, entblockt AP-14*
   - `run.sh` mit identischer Logik wie `run.ps1` spiegeln: venv-Integrität (nicht nur Existenz), idempotenter selbstheilender Install + `pip check`, Status-Helfer (`_ok/_warn/_info/_hdr/_fail`), Port-Check via `ss`/`lsof`.
   - **`|| true` in `do_start`/`do_skip_setup` entfernen** → Exit-Codes sauber durchreichen.
   - **NO-CDN auf Linux:** braucht ein **Linux-Wheelhouse (manylinux-cp314)** — aktuelle `wheels/` sind `win_amd64`! Quelle/Strategie entscheiden (5 C-Ext: sqlalchemy, greenlet, markupsafe, psycopg2-binary, pyodbc).
   - Funktionale Verifikation: simulierte Abbrüche (halbes venv, fehlendes Wheel → Protokoll+Abbruch, Port belegt).
   - Betroffen: `run.sh`.

2. **AP-14 — Python-3.14 Linux/AppImage** — *nach AP-15-Wheelhouse*
   - `run.sh _bundle_python_standalone` bundelt System-Python → auf der Linux-Build-Maschine **3.14** bereitstellen, AppImage gegen 3.14 bauen.
   - Abschluss: `sync_version.py`-Bump + CHANGELOG + AP nach `todo-erledigt.md`.

3. **AP-12 — MSSQL real testbar** (Backend ist fertig)
   - System-ODBC einrichten: `unixODBC` + `msodbcsql18`.
   - Optionaler **Integrationstest** gegen lokale MSSQL-Instanz (markiert/überspringbar, wenn Treiber fehlt).

4. **Zensical-Doku-Site neu bauen** (nur auf Linux möglich) — *am Ende bündeln*
   - Mehrere Doku-Quellen wurden geändert (`usecases.md` u.a.) + **AP-Diagramm** neu bauen. Offene DoD-Schuld aus mehreren APs → einmal sammeln, einmal rebuilden.

5. **AP-17-Rest** (optional): Delivery-Ordner / öffentliche Sicherheits-Notiz.

**Konventionen (Memory):** Deutsch · Doku-Build nur Linux · NO-CDN / nur lokale Sourcen · 1.0.0 nur auf Ansage (sonst Feature→minor / Fix→patch) · vor Arbeit `git fetch`+Divergenz · bei ~70% Kontext zum Handoff warnen · **Commits ohne KI-Signatur (AP-17)**.
**Hinweis:** `run.ps1` NICHT anfassen (Windows/PS-5.1/ASCII+BOM-Constraint) — diese Session ist Linux-only.

**Definition of Done (jedes AP):** Code + Tests grün · betroffene Doku (CLAUDE.md + Zensical) · `sync_version.py`-Bump + CHANGELOG · AP nach `todo-erledigt.md` · AP-Diagramm + Site **auf Linux** neu bauen.

Handoff-Detail: `docs/handoffs/2026-06-26-1845.md` · Backlog: `todo.md`
