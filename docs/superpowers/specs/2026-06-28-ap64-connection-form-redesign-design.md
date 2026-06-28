# AP-64 — Verbindungsform-Umbau — Design

**Datum:** 2026-06-28
**Status:** Spec (genehmigt im Brainstorming)
**Aufwand:** S (reine Frontend-/CSS-Änderung; ein bestehender Endpoint wird wiederverwendet)

## Ziel

Das Verbindungsformular (Tab „Verbindungen", `openConnections` in `web/static/js/app.js`) sauberer ausrichten und Test-vs-Speichern trennen:
- Die **„Name"-Zeile** richtet sich an den Feldern darüber aus.
- Der **„Verbinden"-Button entfällt**.
- **„Speichern"** rückt unter die Felder, links daneben ein neuer **„Testen"**-Button.
- **Unter den Buttons** ein **Infofeld** für das Testergebnis.

## Code-Befunde (Ist-Stand verifiziert)

- `openConnections` (`web/static/js/app.js:1766`) rendert `.conn-form` mit `.row`-Zeilen (Label + Feld). Die Aktionszeile ist heute `<div class="row"><button id="conn_connect">Verbinden</button><input id="conn_name" placeholder="Name zum Speichern"><button id="conn_save">Speichern</button></div>` — **ohne Label**, daher beginnt das Name-Feld am linken Rand und fluchtet nicht.
- CSS (`web/static/css/app.css:35–40`): `.conn-form .row { display:flex; gap:.5rem; align-items:center }`, `.conn-form label { width:8.5rem; flex:0 0 auto }`, Felder `flex:1`. (AP-60 feste Label-Spalte.)
- `/api/connect` (`web/routes.py:69`) baut die URL **und testet** die Verbindung (`SqlAlchemyLoader(url).load()`) → 200 `{connection_url}` bei Erfolg, 400 `{error}` sonst. **Wiederverwendbar als „Testen"** — kein neuer Endpoint nötig.
- `doConnect()` lädt nach erfolgreichem Connect das Schema in die UI. Wird vom Testen-Button **nicht** aufgerufen.

## 1. Layout (`openConnections`-HTML)

Unverändert: Zeilen *Gespeichert*, *Typ*, `#conn_fields`. Danach:

1. **Neue „Name"-Zeile** als reguläre `.row` (fluchtet automatisch):
   ```html
   <div class="row"><label>Name</label>
     <input id="conn_name" type="text" placeholder="Name zum Speichern"></div>
   ```
2. **`#conn_connect` (Verbinden) wird ersatzlos entfernt.**
3. **Button-Zeile** unter den Feldern, unter die Feldspalte eingerückt:
   ```html
   <div class="conn-actions">
     <button id="conn_test" type="button">Testen</button>
     <button id="conn_save" type="button">Speichern</button></div>
   ```
4. **Infofeld** unter den Buttons (das bestehende `#conn_msg`, eingerückt + als Box):
   ```html
   <p class="hint" id="conn_msg"></p>
   ```

## 2. Verhalten (`app.js`)

- **`conn_test`** (neu): `postJSON("/api/connect", formParams())`.
  - Erfolg → `#conn_msg`: „✓ Verbindung erfolgreich" (Klasse `ok`).
  - Fehler → `#conn_msg`: „Fehler: <message>" (Klasse `err`).
  - **Kein `doConnect`**, kein Schema-Laden, kein `setCurrentUrl`.
  - Während des Tests: „teste…".
- **`conn_save`**: Logik unverändert (Validierung Name nicht leer → `postJSON("/api/connections", {name, …formParams})` → `refreshSavedConnections` → Erfolgsmeldung).
- Der bisherige `conn_connect`-Listener entfällt. Die übrigen Listener (`conn_load_saved`, `conn_delete_saved`, `conn_type`-change) bleiben.
- Schema-Laden läuft über die **Topbar** (gespeicherte Verbindung wählen → „Verbinden") — unverändert.

## 3. CSS (`web/static/css/app.css`)

```css
.conn-form .conn-actions { display: flex; gap: .5rem; margin: .5rem 0; margin-left: 9rem; }
.conn-form #conn_msg { margin-left: 9rem; }
.conn-form #conn_msg.ok  { color: #2ea043; }
.conn-form #conn_msg.err { color: #d2322d; }
```
`9rem` = Label-Spalte `8.5rem` + `.5rem` Flex-Gap → Buttons/Infofeld fluchten unter der Feldspalte. Keine externen Assets (NO-CDN).

## 4. Tests

**Browser-Smoke (Playwright, System-python3, gegen laufende App):**
- Verbindungen-Tab öffnen (`openConnections`).
- **Ausrichtung:** linke Kante von `#conn_name` == linke Kante eines `#conn_fields`-Inputs (z. B. Host), Toleranz ≤ 1px (`getBoundingClientRect().left`).
- **Verbinden weg:** `#conn_connect` existiert nicht.
- **Buttons:** `#conn_test` und `#conn_save` existieren, liegen **unter** der letzten Feldzeile (größeres `top`).
- **Infofeld:** `#conn_msg` existiert, liegt unter den Buttons.
- **Testen-Erfolg:** Typ SQLite + Demo-Dateipfad → Testen → `#conn_msg` enthält „erfolgreich" und hat Klasse `ok`; Schema wurde **nicht** geladen (kein Tab-/Sidebar-Wechsel; `SCHEMA` unverändert/leer).
- **Testen-Fehler:** Typ Oracle + unerreichbarer Host → Testen → `#conn_msg` Klasse `err` mit Fehlertext.

App-Neustart vor dem Smoke (Template/JS ist live, aber zur Sicherheit frischer Stand).

## 5. Scope-Cuts / Nicht-Scope

- Kein neuer Backend-Endpoint (`/api/connect` wird wiederverwendet).
- Kein Schema-Laden aus dem Formular (bewusst über die Topbar).
- Keine Änderung an `/api/connections` (Speichern), `build_url`, `formParams`, `renderConnFields`.
- Kein Multi-Filter/sonstige Funktionserweiterung.

## 6. Release / Doku (nach Implementierung)

- `sync_version.py --patch` (UI-Politur, kein neues Feature) + icon-rail `APP_VERSION`/`TEST_COUNT` (Testzahl unverändert, falls kein pytest-Test dazukommt — Smoke ist nicht in der Suite).
- Changelog EN+DE, Roadmap-Versionslog (AP-64), oberflaeche.md (Verbindungsform-Beschreibung), Projekt-Kennzahlen-Seite (Version), Site-Build, gh-pages.
- Deutsch / NO-CDN / Browser-Smoke nicht weglassen.
