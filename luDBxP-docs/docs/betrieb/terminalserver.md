# Betrieb auf einem Terminalserver (Multi-User)

Seit **v0.33.0** kann der DB Explorer von **mehreren Nutzern gleichzeitig** auf
einer Maschine betrieben werden — z. B. auf einem Windows-RDS-/Terminalserver oder
einem Linux-Mehrbenutzer-Host. Diese Seite beschreibt, was die App pro Nutzer
**automatisch** trennt, was der Administrator **einmalig** einrichtet und was
(noch) manuell ist.

## Was die App pro Nutzer automatisch trennt

Ohne Konfiguration laufen zwei Nutzer kollisionsfrei nebeneinander:

- **Port pro Session.** Jede Instanz versucht zuerst Port **5057**; ist er belegt,
  wählt sie automatisch einen **freien** Port. Die tatsächliche URL wird beim Start
  ausgegeben (Konsole **und** Log). Es wird ausschließlich an `127.0.0.1` gebunden —
  **kein** Zugriff von anderen Rechnern.
- **`config.json` + Logs pro Nutzer.** Gespeicherte Verbindungen und Logdateien
  liegen im **Nutzerverzeichnis** des OS (siehe Tabelle unten), nicht im
  App-Verzeichnis. Nutzer überschreiben sich also nicht gegenseitig, und das
  App-Verzeichnis darf **schreibgeschützt** sein (z. B. unter `Program Files`).
- **Einmalige Übernahme.** Existiert beim ersten Start noch eine alte
  `config.json` im App-Verzeichnis, wird sie **einmalig** in den Pro-Nutzer-Pfad
  übernommen (nie überschrieben).

## Einmaliges Administrator-Setup

1. **App + Laufzeitumgebung an einen gemeinsamen Ort** legen (für die Nutzer
   schreibgeschützt zulässig, z. B. `C:\Program Files\LucentTools DB Explorer\`
   bzw. `/opt/luDBxP/`).
2. **venv einrichten** (einmalig, mit Schreibrechten):
   - Windows: `\.run.ps1 -Action setup-venv`
   - Linux: `bash run.sh --setup-venv`
3. **Start-Verknüpfung pro Nutzer** anlegen, die den App-Start im
   *skip-setup*-Modus aufruft (kein erneuter venv-Aufbau pro Nutzer):
   - Windows: `\.run.ps1 -Action skip-setup`
   - Linux: `bash run.sh --skip-setup`

Da Daten pro Nutzer im Profil landen, ist **keine** weitere Pro-Nutzer-Einrichtung
nötig.

## Start pro Nutzer

| Plattform | Befehl | Ergebnis |
|---|---|---|
| Windows | `\.run.ps1 -Action skip-setup` | startet die App; freier Port wird gewählt, URL wird ausgegeben |
| Linux | `bash run.sh --skip-setup` | dito |

Die Launcher **brechen bei belegtem Port nicht mehr ab** — sie weisen darauf hin,
dass automatisch ein freier Port gewählt wird, und starten durch. Jeder Nutzer
öffnet die in seiner Konsole/seinem Log angezeigte URL (`http://127.0.0.1:<Port>`).

## Ein-Klick-Start (Tray, seit v0.34.0)

Statt einer Konsole kann pro Nutzer eine **Verknüpfung** angelegt werden, deren Ziel
`run.ps1 -Action tray` (Windows) bzw. `run.sh --tray` (Linux) ist. Beim **ersten** Klick wird
das venv automatisch eingerichtet (Fortschritt kurz sichtbar) — der **Nutzer muss nichts
einrichten**; danach startet ein **fensterloses Tray-Icon** und der Browser öffnet sich
automatisch, sobald der Server antwortet. Tray-Menü: **Im Browser öffnen**, **Info**
(Version/URL/Port), **Beenden** (stoppt die App → Port frei). Spätere Starts gehen direkt durch.

> Hinweis: Die `tray`-Action wurde der signierten `run.ps1` hinzugefügt → einmalige
> **Re-Signatur** nötig. Ein `.exe`-Bau ist nicht erforderlich.

## Pro-Nutzer-Pfade

| Inhalt | Windows | Linux/mac |
|---|---|---|
| `config.json` | `%LOCALAPPDATA%\luDBxP\config.json` | `~/.config/luDBxP/config.json` (bzw. `$XDG_CONFIG_HOME`) |
| Logs (`app.log`) | `%LOCALAPPDATA%\luDBxP\Logs\` | `~/.local/state/luDBxP/logs/` (bzw. `$XDG_STATE_HOME`) |

## Umgebungsvariablen

Alle optional — für Standard-Betrieb ist nichts zu setzen.

| Variable | Wirkung |
|---|---|
| `LUCENT_PORT` | fester Port (`<n>`) erzwingen, oder `0` für *immer dynamisch*. Ohne Variable: 5057 bevorzugt, sonst freier Port. |
| `LUCENT_CONFIG_DIR` | Verzeichnis für `config.json` überschreiben (z. B. ein verbundenes Netzlaufwerk). |
| `LUCENT_LOG_DIR` | Log-Verzeichnis überschreiben. |
| `LUCENT_LOG_LEVEL` | `DEBUG`/`INFO`/… (Standard `INFO`). |
| `LUCENT_DEBUG` | truthy ⇒ Debug-Level + Flask-Debugger (nur lokal/Diagnose; **nicht** im Mehrbenutzerbetrieb). |

## Sicherheit

- **Nur `127.0.0.1`.** Kein Bind an `0.0.0.0` — eine Instanz ist nur in der
  eigenen Session erreichbar, nicht von außen.
- **Read-only-Werkzeug.** Es werden ausschließlich Schema-Metadaten gelesen und
  SQL-Strings erzeugt/ausgeführt im Lesemodus; es findet **keine** Mutation der
  Datenbank statt (kein INSERT/UPDATE/DELETE/DDL).
- **Keine Passwörter persistiert.** Gespeicherte Verbindungen enthalten **kein**
  Passwort.

## Prozess-Lebenszyklus & Port-Freigabe

Ein gewählter Port bleibt für die **gesamte Laufzeit** des Server-Prozesses
gebunden und wird erst frei, wenn der Prozess endet (Strg+C, Fenster schließen,
Prozess beenden, Session-Ende) — **Browser schließen genügt nicht**. Auf einem
Terminalserver sollten Nutzer die App daher **sauber beenden**, damit Port und RAM
freigegeben werden. Ein automatischer Idle-Shutdown ist noch nicht implementiert
(siehe unten).

## Noch nicht automatisiert (geplant)

Die folgenden AP-31-Bausteine sind bewusst **noch offen** und für den Betrieb zu
beachten:

- **Produktions-WSGI-Server (waitress).** Aktuell läuft der Flask-Entwicklungs­server
  (mit `threaded=True`). Für Dauerbetrieb mit vielen Nutzern ist ein lokaler
  WSGI-Server vorgesehen.
- **Idle-Shutdown / „Beenden"-Aktion.** Automatisches Freigeben von Port/RAM nach
  Inaktivität ist geplant (Bezug Tray-Icon-Launcher).
- **Verteilung/Härtung.** Shared read-only venv, signierte `run.ps1` (AllSigned)
  und eine Startmenü-Verknüpfung pro Nutzer sind als eigene Scheibe vorgesehen.

## Troubleshooting

- **„Port belegt" beim Start?** Kein Fehler mehr — die App wählt automatisch einen
  freien Port. Die gültige URL steht in der Konsole bzw. im Log.
- **Wo liegt meine `config.json`/mein Log?** Siehe Tabelle *Pro-Nutzer-Pfade*; mit
  `LUCENT_CONFIG_DIR`/`LUCENT_LOG_DIR` umlenkbar.
- **Alle sollen einen festen Port nutzen?** Nicht empfehlenswert auf einem geteilten
  Loopback (Kollision). Falls doch nötig, `LUCENT_PORT=<n>` pro Nutzer unterschiedlich
  setzen.
