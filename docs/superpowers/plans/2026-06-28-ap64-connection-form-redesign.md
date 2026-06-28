# AP-64 — Verbindungsform-Umbau Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Verbindungsformular ausrichten und Test-vs-Speichern trennen: Name-Zeile fluchtet, „Verbinden" entfällt, `[Testen] [Speichern]` unter den Feldern, Infofeld darunter.

**Architecture:** Reine Frontend-Änderung in `openConnections` (`web/static/js/app.js`) + CSS (`web/static/css/app.css`). „Testen" ruft den bestehenden `/api/connect`-Endpoint (baut URL + testet via `.load()`) und zeigt das Ergebnis im Infofeld, ohne ein Schema zu laden. Kein Backend-Change.

**Tech Stack:** Vanilla JS, CSS, Playwright-Smoke (System-python3).

**Spec:** `docs/superpowers/specs/2026-06-28-ap64-connection-form-redesign-design.md`

## Global Constraints

- **NO CDN:** keine externen `<script>`/`<link>`; nur bestehende lokale Assets.
- **UI-Texte Deutsch.**
- **Read-only:** unberührt — `/api/connect` testet nur (reflektiert Metadaten), schreibt nie.
- **Kein neuer Backend-Endpoint**, keine Änderung an `/api/connect`, `/api/connections`, `build_url`, `formParams`, `renderConnFields`.
- **Version:** `config.APP_VERSION` nie von Hand — nur via `./venv/bin/python sync_version.py --patch`.
- **Tests:** `./venv/bin/python -m pytest` (venv = Python 3.14). Baseline: **356 passed, 2 skipped** (bleibt unverändert — der Browser-Smoke ist nicht Teil der pytest-Suite).
- **Branch:** `ap-64-conn-form` (bereits angelegt, Spec committet `fc44131`).

---

### Task 1: Verbindungsform — Layout, Testen-Verhalten, CSS

**Files:**
- Modify: `web/static/js/app.js` (`openConnections`, ~Zeilen 1770–1804)
- Modify: `web/static/css/app.css` (nach Zeile 40)
- Smoke: `.superpowers/sdd/verify_connform.py` (neu)

**Interfaces:**
- Consumes: bestehende Helfer `ensureTab`, `postJSON`, `formParams`, `refreshSavedConnections`, `renderConnFields`, `$`, `DB_TYPES`, `SAVED_CONNS`; Endpoint `/api/connect`.
- Produces: Form-IDs `conn_name`, `conn_test`, `conn_save`, `conn_msg`; CSS-Klasse `conn-actions`; Farbklassen `#conn_msg.ok`/`.err`.

- [ ] **Step 1: Failing Browser-Smoke schreiben**

Create `.superpowers/sdd/verify_connform.py`:
```python
"""Browser smoke for AP-64: connection form — Name aligned, no 'Verbinden',
[Testen][Speichern] below fields, info box below buttons; Testen tests only."""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5057/"
DEMO = "/home/meagle/Dokumente/_Projects/lucent-job-luDBxP/sample_data/demo_cmdb.db"

results = []
def check(n, ok, d=""):
    results.append((n, ok)); print(("PASS" if ok else "FAIL"), n, ("- " + d) if d else "")

def launch(p):
    last = None
    for kw in ({"executable_path": "/usr/bin/chromium"}, {"executable_path": "/usr/bin/google-chrome"}, {}):
        try: return p.chromium.launch(headless=True, **kw)
        except Exception as e: last = e
    raise last

with sync_playwright() as p:
    b = launch(p); page = b.new_page(viewport={"width": 1400, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(f"{m.text} [{m.location.get('url','')}]") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until="networkidle")
    page.evaluate("openConnections()")
    page.wait_for_selector("#tabpanels .conn-form", timeout=5000)

    # No 'Verbinden' button in the form
    check("conn_connect entfernt", page.evaluate("!document.getElementById('conn_connect')"))

    # Test/Save buttons + info field exist
    for id_ in ("conn_test", "conn_save", "conn_name", "conn_msg"):
        check(f"#{id_} vorhanden", page.evaluate(f"!!document.getElementById('{id_}')"))

    # Alignment: select a network type so cf_host exists, compare left edges
    page.evaluate("""() => { const s=document.getElementById('conn_type'); s.value='oracle';
        s.dispatchEvent(new Event('change')); }""")
    page.wait_for_selector("#cf_host", timeout=3000)
    geo = page.evaluate("""() => {
        const r = (id) => document.getElementById(id).getBoundingClientRect();
        return {name: r('conn_name').left, host: r('cf_host').left,
                btnTop: r('conn_test').top, nameTop: r('conn_name').top,
                msgTop: r('conn_msg').top, saveTop: r('conn_save').top}; }""")
    check("Name fluchtet mit Feldern (≤1px)", abs(geo["name"] - geo["host"]) <= 1,
          f"name={geo['name']} host={geo['host']}")
    check("Buttons unter den Feldern", geo["btnTop"] > geo["nameTop"])
    check("Infofeld unter den Buttons", geo["msgTop"] >= geo["saveTop"])

    # Testen error: unreachable Oracle host
    page.evaluate("""() => { document.getElementById('cf_host').value='nonexistent.invalid';
        document.getElementById('cf_service_name').value='X';
        document.getElementById('cf_user').value='u'; document.getElementById('cf_password').value='p'; }""")
    page.evaluate("document.getElementById('conn_test').click()")
    page.wait_for_function("document.getElementById('conn_msg').classList.contains('err')", timeout=15000)
    check("Testen-Fehler → #conn_msg.err", True)

    # Testen success: sqlite demo; schema must NOT load
    page.evaluate("""(db) => { const s=document.getElementById('conn_type'); s.value='sqlite';
        s.dispatchEvent(new Event('change')); document.getElementById('cf_filepath').value=db; }""", DEMO)
    page.evaluate("document.getElementById('conn_test').click()")
    page.wait_for_function("document.getElementById('conn_msg').classList.contains('ok')", timeout=15000)
    txt = page.eval_on_selector("#conn_msg", "el => el.textContent")
    check("Testen-Erfolg → #conn_msg.ok 'erfolgreich'", "erfolgreich" in txt)
    no_schema = page.evaluate("!(window.SCHEMA && SCHEMA.tables && SCHEMA.tables.length > 0)")
    check("Testen lädt KEIN Schema", no_schema)

    real = [e for e in errors if "favicon" not in e.lower()]
    check("keine Konsolenfehler", not real, "; ".join(real[:3]))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results)-len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
```

- [ ] **Step 2: App starten + Smoke laufen lassen, Fehlschlag bestätigen**

```bash
LUCENT_PORT=5057 bash run.sh --skip-setup   # laufende Instanz vorher beenden
```
Run: `python3 .superpowers/sdd/verify_connform.py`
Expected: FAIL — `#conn_connect` existiert noch, `#conn_test` fehlt, Name fluchtet nicht.

- [ ] **Step 3: `openConnections`-HTML umbauen**

In `web/static/js/app.js`, in `openConnections`, den `panel.innerHTML =`-Block (von `` `<div class="detail conn-form">… `` bis `…conn_msg"></p></div>`;`) **ersetzen** durch:
```js
  panel.innerHTML =
    `<div class="detail conn-form"><h2>Verbindung</h2>` +
    `<div class="row"><label>Gespeichert</label>` +
    `<select id="conn_saved"></select>` +
    `<button id="conn_load_saved" type="button">Laden</button>` +
    `<button id="conn_delete_saved" type="button">Löschen</button></div>` +
    `<div class="row"><label>Typ</label><select id="conn_type">` +
    DB_TYPES.map((t) => `<option value="${t.v}">${t.label}</option>`).join("") +
    `</select></div>` +
    `<div id="conn_fields"></div>` +
    `<div class="row"><label>Name</label>` +
    `<input id="conn_name" type="text" placeholder="Name zum Speichern"></div>` +
    `<div class="conn-actions">` +
    `<button id="conn_test" type="button">Testen</button>` +
    `<button id="conn_save" type="button">Speichern</button></div>` +
    `<p class="hint" id="conn_msg"></p></div>`;
```

- [ ] **Step 4: `conn_connect`-Listener durch `conn_test` ersetzen**

In `openConnections` den bestehenden Block
```js
  $("conn_connect").addEventListener("click", async () => {
    $("conn_msg").textContent = "verbinde…";
    try {
      const r = await postJSON("/api/connect", formParams());
      setCurrentUrl(r.connection_url);
      await doConnect();
    } catch (e) { $("conn_msg").textContent = "Fehler: " + e.message; }
  });
```
**ersetzen** durch (Testen testet nur, lädt kein Schema):
```js
  $("conn_test").addEventListener("click", async () => {
    const msg = $("conn_msg");
    msg.className = "hint"; msg.textContent = "teste…";
    try {
      await postJSON("/api/connect", formParams());
      msg.className = "hint ok"; msg.textContent = "✓ Verbindung erfolgreich";
    } catch (e) {
      msg.className = "hint err"; msg.textContent = "Fehler: " + e.message;
    }
  });
```

- [ ] **Step 5: `conn_save`-Listener — Farbklasse mitsetzen (Stale-Color vermeiden)**

Den bestehenden `conn_save`-Listener so anpassen, dass er die `#conn_msg`-Klasse passend setzt (sonst bleibt eine vorherige `err`/`ok`-Farbe stehen). Ersetze
```js
  $("conn_save").addEventListener("click", async () => {
    const name = $("conn_name").value.trim();
    if (!name) { $("conn_msg").textContent = "Name zum Speichern angeben."; return; }
    try {
      await postJSON("/api/connections", Object.assign({ name }, formParams()));
      await refreshSavedConnections();
      $("conn_saved").value = name;
      $("conn_msg").textContent = `„${name}" gespeichert (ohne Passwort).`;
    } catch (e) { $("conn_msg").textContent = "Fehler: " + e.message; }
  });
```
durch
```js
  $("conn_save").addEventListener("click", async () => {
    const msg = $("conn_msg");
    const name = $("conn_name").value.trim();
    if (!name) { msg.className = "hint err"; msg.textContent = "Name zum Speichern angeben."; return; }
    try {
      await postJSON("/api/connections", Object.assign({ name }, formParams()));
      await refreshSavedConnections();
      $("conn_saved").value = name;
      msg.className = "hint ok"; msg.textContent = `„${name}" gespeichert (ohne Passwort).`;
    } catch (e) { msg.className = "hint err"; msg.textContent = "Fehler: " + e.message; }
  });
```

- [ ] **Step 6: CSS ergänzen**

In `web/static/css/app.css` direkt nach der Zeile `.conn-form #conn_msg { min-height: 1.2em; }` (Zeile 40) einfügen:
```css
/* AP-64: Aktionszeile + Infofeld unter die Feldspalte (Label 8.5rem + .5rem Gap) */
.conn-form .conn-actions { display: flex; gap: .5rem; margin: .5rem 0; margin-left: 9rem; }
.conn-form #conn_msg { margin-left: 9rem; }
.conn-form #conn_msg.ok  { color: #2ea043; }
.conn-form #conn_msg.err { color: #d2322d; }
```

- [ ] **Step 7: App neu starten (JS live, aber Smoke lädt frisch) + Smoke laufen lassen, Erfolg bestätigen**

JS/CSS sind live; ein Reload reicht. Falls keine Instanz läuft, wie Step 2 starten.
Run: `python3 .superpowers/sdd/verify_connform.py`
Expected: `12/12 checks passed`.

- [ ] **Step 8: Volle pytest-Suite (Regressionsschutz)**

Run: `./venv/bin/python -m pytest -q 2>&1 | tail -1`
Expected: `356 passed, 2 skipped` (unverändert — reine Frontend-Änderung).

- [ ] **Step 9: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css .superpowers/sdd/verify_connform.py
git commit -m "feat: AP-64 — Verbindungsform: Name ausgerichtet, Testen+Speichern, Infofeld (Verbinden entfällt)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Release v0.48.1 + Doku/Übersichten + Deploy

**Files:** `config.py`, `lucent-hub.yml` (sync_version); `luDBxP-docs/docs/javascripts/icon-rail.js`; `luDBxP-docs/zensical.toml`; `CHANGELOG.md` + `luDBxP-docs/docs/entwicklung/changelog.md`; `luDBxP-docs/docs/projekt/roadmap.md`; `luDBxP-docs/docs/referenz/oberflaeche.md`; `docs/projekt-kennzahlen.html` + `luDBxP-docs/docs/projekt/kennzahlen.md`; Site-Build.

- [ ] **Step 1: Version-Bump (PATCH)**

```bash
./venv/bin/python sync_version.py --patch    # 0.48.0 → 0.48.1
./venv/bin/python -m pytest -q 2>&1 | tail -1  # bestätigt 356 passed (TEST_COUNT bleibt 356)
```

- [ ] **Step 2: icon-rail + zensical**

`luDBxP-docs/docs/javascripts/icon-rail.js`: `APP_VERSION` → `'0.48.1'` (`TEST_COUNT` bleibt `'356'`, `TEST_DATE` bleibt `'2026-06-28'`).
`luDBxP-docs/zensical.toml`: `· v0.48.0` → `· v0.48.1`.

- [ ] **Step 3: Changelog EN** (`CHANGELOG.md` oben)

```markdown
## [0.48.1] — 2026-06-28

### Changed
- Connection form reworked (AP-64): the save-name field now aligns with the
  fields above it; the old "Verbinden" button is gone; a new "Testen" button
  (left of "Speichern", below the fields) tests the connection read-only and
  reports the result in an info box below the buttons. Loading a schema stays a
  topbar action on a saved connection. No backend change (reuses `/api/connect`).
```

- [ ] **Step 4: Changelog-Mirror DE** (`luDBxP-docs/docs/entwicklung/changelog.md` oben)

```markdown
## [0.48.1] — 2026-06-28

### Geändert
- Verbindungsformular überarbeitet (AP-64): das Feld „Name zum Speichern" fluchtet
  jetzt mit den Feldern darüber; der alte „Verbinden"-Button entfällt; ein neuer
  „Testen"-Button (links von „Speichern", unter den Feldern) prüft die Verbindung
  read-only und zeigt das Ergebnis in einem Infofeld unter den Buttons. Das Laden
  eines Schemas bleibt eine Topbar-Aktion auf einer gespeicherten Verbindung.
  Keine Backend-Änderung (nutzt `/api/connect`).
```

- [ ] **Step 5: roadmap.md — v0.48.1-Versionslog**

In `luDBxP-docs/docs/projekt/roadmap.md` unter „## Erledigte Arbeitspakete" **vor** dem `**v0.48.0**`-Block einfügen:
```markdown
**v0.48.1** (2026-06-28):

- **AP-64** — Verbindungsform-Umbau: Name-Feld fluchtet mit den Feldern, „Verbinden" entfällt, neuer „Testen"-Button (read-only via `/api/connect`) + „Speichern" unter den Feldern, Infofeld darunter. Nur Frontend/CSS. **Aufwand S** — v0.48.1
```

- [ ] **Step 6: oberflaeche.md**

In `luDBxP-docs/docs/referenz/oberflaeche.md` im Verbindungs-Abschnitt die Beschreibung anpassen: das Verbindungsformular hat jetzt ein ausgerichtetes Name-Feld, einen „Testen"-Button (prüft die Verbindung read-only, lädt kein Schema) und „Speichern"; ein Infofeld unter den Buttons zeigt das Ergebnis. Schema-Laden erfolgt über die Topbar-Verbindungsauswahl.

- [ ] **Step 7: Projekt-Kennzahlen (nur Version)**

`docs/projekt-kennzahlen.html` UND `luDBxP-docs/docs/projekt/kennzahlen.md`: Version `v0.48.0` → `v0.48.1` (Tests/Coverage unverändert — keine pytest-Änderung). Restliche Werte unangetastet.

- [ ] **Step 8: Site bauen + gegenprüfen**

```bash
./luDBxP-docs/.venv-docs/bin/python luDBxP-docs/build_docs.py
grep -o "v0.48.1" luDBxP-docs/site/index.html | head -1
```
Expected: `v0.48.1`.

- [ ] **Step 9: SDD-Final-Review** (Controller, über `git diff master...ap-64-conn-form`): NO-CDN, read-only, Doku-Vollständigkeit, keine Test-Regression.

- [ ] **Step 10: Commit Doku/Version**

```bash
git add -A
git commit -m "docs: Release v0.48.1 — Verbindungsform-Umbau (AP-64)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 11: Merge + Deploy** (nach Freigabe): ff-merge → master, push origin/master, gh-pages-Worktree-Deploy (`.nojekyll` erhalten).

---

## Self-Review

**Spec coverage:**
- §1 Layout (Name-Zeile fluchtet, Verbinden weg, conn-actions, Infofeld) → Task 1 Step 3 ✓
- §2 Verhalten (Testen via /api/connect, kein doConnect; Speichern unverändert + Farbklasse) → Task 1 Step 4/5 ✓
- §3 CSS (conn-actions + #conn_msg eingerückt + ok/err) → Task 1 Step 6 ✓
- §4 Tests (Smoke: Ausrichtung, kein conn_connect, Buttons/Infofeld, Testen-Erfolg/-Fehler, kein Schema-Load) → Task 1 Step 1 ✓
- §5 Scope-Cuts (kein neuer Endpoint, kein Schema-Load aus Formular) → eingehalten ✓
- §6 Release/Doku (PATCH) → Task 2 ✓

**Placeholder scan:** keine TBD; alle Code-Hunks vollständig, Commands mit Expected.

**Type/Name-Konsistenz:** IDs `conn_name`/`conn_test`/`conn_save`/`conn_msg`, Klasse `conn-actions`, Farbklassen `hint ok`/`hint err` (CSS `#conn_msg.ok`/`.err`) — identisch in HTML (Step 3), Listenern (Step 4/5), CSS (Step 6) und Smoke (Step 1). `/api/connect` + `formParams` unverändert genutzt.
