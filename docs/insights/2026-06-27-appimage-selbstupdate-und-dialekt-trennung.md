# Insight 2026-06-27 — AppImage-Selbstupdate & „Anzeige ≠ Ausführung"

Zwei generalisierbare Erkenntnisse aus der AP-14/AP-29-Arbeit.

## 1. „Copy-on-first-run" ohne Versionsabgleich liefert stillen Alt-Code

**Symptom (real beobachtet):** Eine frisch als **v0.14.0** gebaute AppImage zeigte
im Browser **v0.1.0** an. Kein falscher Build — die AppRun-Logik kopierte den
App-Code nur **beim Erststart** in ein schreibbares Verzeichnis
(`if [ ! -f "$APP_WORK/app.py" ]`) und **aktualisierte nie**. Ein Überbleibsel
vom Vortag wurde weiter ausgeführt.

**Lektion:** Jeder „kopiere App in schreibbares Verzeichnis"-Installer (AppImage,
Portable-App, First-Run-Bootstrap) braucht einen **Versions-Stamp** und ein
Update bei Versionswechsel — sonst läuft alter Code unter neuem Etikett.
**Pattern:** Bundle-Version aus `config` lesen, mit `.app_version`-Stamp im
Zielordner vergleichen; bei Abweichung **Code-Teile** frisch kopieren,
**Nutzerdaten** (config.json, Logs) explizit ausnehmen, Stamp neu schreiben.

**Verschärfend:** Der Build meldete „erfolgreich", obwohl ein Diagramm-Render
scheiterte — weil `mmdc … | tail` den Exit-Code maskierte (`set -e` greift nicht
hinter der Pipe). **Silent-failure-Regel:** Exit-Codes nie durch `| tail`/`| head`
verschlucken; in Logdatei schreiben und den echten Status prüfen.

## 2. SQL-Dialekt: Anzeige-Dialekt ≠ Ausführungs-Dialekt

Beim Dialekt-Umschalter (AP-29) ist die nicht-offensichtliche Falle: Der Nutzer
darf jeden Dialekt zum **Kopieren** anzeigen (Oracle `FETCH FIRST`, MSSQL
`[…]`/`TOP`), aber **ausgeführt** werden muss gegen das **echte** Backend.
Würde man die Anzeige-Variante ausführen, crasht z. B. Oracle-SQL auf SQLite.
**Pattern:** zwei getrennte Dialekt-Quellen — Anzeige aus der UI-Wahl, Ausführung
aus dem Verbindungs-Scheme abgeleitet (`_dialect_from_url`).

## 3. Test-Instanz ohne Docker: rootless Podman

`docker.io` kollidierte (`containerd.io` vs `containerd`, eingeschleppt übers
frisch hinzugefügte MS-Paket-Repo). **Rootless Podman** war bereits da, lief ohne
sudo, band Port 1433 und zog das `mcr.microsoft.com/mssql/server:2022`-Image —
saubere Docker-Alternative für lokale Integrations-Test-Instanzen.

Bezug: `docs/handoffs/2026-06-27-0028.md` · APs 14/29/12.
