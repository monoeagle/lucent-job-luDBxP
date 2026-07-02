# AP-70 — Oracle SID/Service-Verbindung — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Oracle-Verbindungen lassen sich per SID **oder** Service-Name adressieren (Easy-Connect), wählbar in der Verbindungsmaske.

**Architecture:** `core/connection.py::build_url` bekommt einen `oracle_connect_type`-Zweig (service→`?service_name=`, sid→URL-**Pfad**); die JS-Maske togglet per Dropdown das aktive Feld; die Persistenz-Whitelist speichert die zwei neuen Felder. Thin-Mode bleibt Default (kein `init_oracle_client`).

**Tech Stack:** Python 3.14, SQLAlchemy (`oracle+oracledb`, Thin), Flask, vanilla JS, pytest, Playwright (System-python3).

## Global Constraints

- **SID gehört in den URL-Pfad**, NICHT in die Query: `oracle+oracledb://u:p@host:port/<SID>`. Die `?sid=`-Form erzeugt einen kaputten DSN (`dsn='host'`) — empirisch verifiziert. Service-Name bleibt `?service_name=<svc>`.
- **Kein `oracledb.init_oracle_client(...)`** irgendwo einbauen — Thin-Mode ist Default (AP-53) und bleibt.
- `oracle_connect_type` Default = `"service"` (fehlt das Feld → rückwärtskompatibel zu gespeicherten Verbindungen mit nur `service_name`).
- Fehlermeldungen deutsch. NO-CDN (keine externen JS/CSS). Read-only-Prinzip unberührt.
- Version: `sync_version.py --minor` → **v0.68.0** (nie Version von Hand editieren).
- Branch: `feat/ap70-oracle-sid-service` (existiert, Spec bereits committet).

---

### Task 1: `build_url` — Oracle SID/Service-Zweig

**Files:**
- Modify: `core/connection.py` (Oracle-Zweig in `build_url`, aktuell ~Zeile 80–88)
- Test: `tests/test_connection.py`

**Interfaces:**
- Consumes: nichts Neues.
- Produces: `build_url(params)` akzeptiert zusätzlich `params["oracle_connect_type"]` ∈ {`"service"`,`"sid"`} und `params["sid"]`. `service`/Default → `oracle+oracledb://{auth}{host}:{port}/?service_name={svc}`; `sid` → `oracle+oracledb://{auth}{host}:{port}/{sid}`.

- [ ] **Step 1: Failing tests schreiben** — an `tests/test_connection.py` anhängen:

```python
def test_oracle_url_with_sid_uses_path_form():
    url = build_url({
        "db_type": "oracle", "host": "h", "sid": "Configdb",
        "oracle_connect_type": "sid", "user": "u", "password": "p"})
    assert url == "oracle+oracledb://u:p@h:1521/Configdb"


def test_oracle_service_explicit_connect_type():
    url = build_url({
        "db_type": "oracle", "host": "h", "service_name": "XEPDB1",
        "oracle_connect_type": "service", "user": "u", "password": "p"})
    assert url == "oracle+oracledb://u:p@h:1521/?service_name=XEPDB1"


def test_oracle_defaults_to_service_when_type_absent():
    # Rückwärtskompatibel: alte gespeicherte Verbindungen ohne oracle_connect_type.
    url = build_url({
        "db_type": "oracle", "host": "h", "service_name": "XEPDB1",
        "user": "u", "password": "p"})
    assert url == "oracle+oracledb://u:p@h:1521/?service_name=XEPDB1"


def test_oracle_missing_sid_raises():
    with pytest.raises(ValueError):
        build_url({"db_type": "oracle", "host": "h", "oracle_connect_type": "sid",
                   "user": "u", "password": "p"})


def test_oracle_unknown_connect_type_raises():
    with pytest.raises(ValueError):
        build_url({"db_type": "oracle", "host": "h", "service_name": "X",
                   "oracle_connect_type": "tns", "user": "u", "password": "p"})


def test_oracle_sid_produces_sid_dsn():
    # Absicherung gegen Rückfall zur kaputten ?sid=-Form: der reale DSN muss SID tragen.
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    url = build_url({
        "db_type": "oracle", "host": "h", "sid": "Configdb",
        "oracle_connect_type": "sid", "user": "u", "password": "p"})
    _, kw = create_engine(url).dialect.create_connect_args(make_url(url))
    assert "SID=Configdb" in kw["dsn"]
    assert "sid" not in kw  # kein loses sid-Kwarg (das war der Draft-Bug)
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `./venv/bin/python -m pytest tests/test_connection.py -k oracle -v`
Expected: die fünf neuen Tests FAIL (SID-Zweig fehlt: liefert `?service_name=`-URL bzw. falsche Fehler), `test_oracle_sid_produces_sid_dsn` FAIL. Die drei alten `test_oracle_*` PASS.

- [ ] **Step 3: Oracle-Zweig implementieren** — in `core/connection.py` den bestehenden Oracle-Block ersetzen:

```python
    if db_type == "oracle":
        # Oracle: address by service name (query) or SID (URL path). Default to
        # service for backward compatibility with saved connections that predate
        # the SID option and carry only service_name.
        connect_type = (params.get("oracle_connect_type") or "service").strip().lower()
        if connect_type == "sid":
            sid = (params.get("sid") or "").strip()
            if not sid:
                raise ValueError("SID fehlt.")
            # SID belongs in the URL path — the ?sid= query form yields a broken
            # DSN (dsn='host', sid as a stray kwarg); the path form produces a
            # correct (CONNECT_DATA=(SID=...)) descriptor.
            return f"{_DRIVERS['oracle']}://{auth}{host}:{port}/{quote_plus(sid)}"
        if connect_type != "service":
            raise ValueError(f"Unbekannte Oracle-Verbindungsart: {connect_type!r}")
        service = (params.get("service_name") or "").strip()
        if not service:
            raise ValueError("Service-Name fehlt.")
        return (f"{_DRIVERS['oracle']}://{auth}{host}:{port}"
                f"/?service_name={quote_plus(service)}")
```

Auch den `build_url`-Docstring (`Args:`) minimal ergänzen: „für Oracle zusätzlich `oracle_connect_type` (service/sid) und `sid`".

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `./venv/bin/python -m pytest tests/test_connection.py -v`
Expected: alle PASS (neue + alte, inkl. `test_oracle_missing_service_name_raises` das dank Default `service` weiter „Service-Name fehlt." wirft).

- [ ] **Step 5: Commit**

```bash
git add core/connection.py tests/test_connection.py
git commit -m "feat(ap-70): build_url Oracle SID (Pfad-Form) + Service-Wahl

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Persistenz-Whitelist (`routes.py`)

**Files:**
- Modify: `web/routes.py` (`_CONN_FIELDS`, Zeile 23–24)
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: Task-1-`build_url` (indirekt via `/api/connect`).
- Produces: gespeicherte Oracle-Verbindungen tragen `sid` + `oracle_connect_type`.

- [ ] **Step 1: Failing test schreiben** — an `tests/test_api.py` anhängen (Muster wie `test_mssql_connection_persists_encrypt_and_trust`):

```python
def test_oracle_connection_persists_sid_and_connect_type(client, tmp_path, monkeypatch):
    """AP-70: Oracle sid + oracle_connect_type werden mitgespeichert."""
    monkeypatch.setenv("LUCENT_CONFIG_DIR", str(tmp_path))
    save = client.post("/api/connections", json={
        "name": "ora_sid", "db_type": "oracle", "host": "h", "port": 1521,
        "sid": "Configdb", "oracle_connect_type": "sid",
        "user": "demo", "password": "SECRET"})
    assert save.status_code == 200
    conns = client.get("/api/connections").get_json()["connections"]
    saved = next(c for c in conns if c["name"] == "ora_sid")
    assert saved.get("sid") == "Configdb"
    assert saved.get("oracle_connect_type") == "sid"
    assert "password" not in saved
    client.delete("/api/connections", json={"name": "ora_sid"})
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `./venv/bin/python -m pytest tests/test_api.py::test_oracle_connection_persists_sid_and_connect_type -v`
Expected: FAIL — `saved.get("sid")` ist `None` (Felder nicht in der Whitelist).

- [ ] **Step 3: Whitelist erweitern** — in `web/routes.py`:

```python
_CONN_FIELDS = ("db_type", "host", "port", "database", "user", "filepath",
                "encrypt", "trust_server_certificate", "service_name",
                "sid", "oracle_connect_type")
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `./venv/bin/python -m pytest tests/test_api.py -k connection -v`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add web/routes.py tests/test_api.py
git commit -m "feat(ap-70): sid + oracle_connect_type in Persistenz-Whitelist

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Verbindungsmaske (`app.js`)

**Files:**
- Modify: `web/static/js/app.js` (`connFieldsHtml` Oracle-Zweig ~Z. 2018–2025; `formParams` Oracle-Zweig ~Z. 2056–2058; neuer Toggle-Handler; `renderConnFields`)

**Interfaces:**
- Consumes: `build_url` (Task 1), Whitelist (Task 2).
- Produces: `formParams()` liefert für Oracle `{oracle_connect_type, service_name, sid, ...}`.

- [ ] **Step 1: Oracle-Maske umbauen** — in `connFieldsHtml`, den Oracle-Zweig (`if (dbType === "oracle") { … }`) ersetzen durch Dropdown + beide Feld-Zeilen (inaktive per `display:none`):

```javascript
  // Oracle: SID oder Service-Name wählbar (AP-70). Beide Felder bleiben im DOM;
  // das inaktive ist ausgeblendet, damit ein Umschalten die Eingaben nicht verwirft.
  if (dbType === "oracle") {
    const ct = c.oracle_connect_type || "service";
    const sel = (v) => (ct === v ? " selected" : "");
    const hide = (v) => (ct === v ? "" : ' style="display:none"');
    html +=
      `<div class="row"><label>Verbindungsart</label>` +
      `<select id="cf_oracle_connect_type">` +
      `<option value="service"${sel("service")}>Service-Name</option>` +
      `<option value="sid"${sel("sid")}>SID</option></select></div>` +
      `<div class="row" id="cf_row_service_name"${hide("service")}>` +
      `<label>Service-Name</label><input id="cf_service_name" type="text" ` +
      `placeholder="XEPDB1" value="${esc(c.service_name || "")}"></div>` +
      `<div class="row" id="cf_row_sid"${hide("sid")}>` +
      `<label>SID</label><input id="cf_sid" type="text" ` +
      `placeholder="ORCL" value="${esc(c.sid || "")}"></div>`;
  } else {
    html += `<div class="row"><label>Datenbank</label><input id="cf_database" type="text" ` +
      `value="${esc(c.database || "")}"></div>`;
  }
```

- [ ] **Step 2: Toggle-Handler in `renderConnFields` verdrahten** — nach dem `innerHTML`-Zuweisen:

```javascript
function renderConnFields(c) {
  $("conn_fields").innerHTML = connFieldsHtml($("conn_type").value, c);
  const sel = $("cf_oracle_connect_type");
  if (sel) {
    sel.addEventListener("change", () => {
      const isSid = sel.value === "sid";
      $("cf_row_service_name").style.display = isSid ? "none" : "";
      $("cf_row_sid").style.display = isSid ? "" : "none";
    });
  }
}
```

- [ ] **Step 3: `formParams` Oracle-Zweig erweitern** — die Zeile `if (t === "oracle") p.service_name = …` ersetzen:

```javascript
  // Oracle sendet Verbindungsart + beide Werte; build_url wählt anhand des Typs.
  if (t === "oracle") {
    p.oracle_connect_type = $("cf_oracle_connect_type").value;
    p.service_name = $("cf_service_name").value;
    p.sid = $("cf_sid").value;
  } else p.database = $("cf_database").value;
```

- [ ] **Step 4: App neu starten (JS ist live, aber sauber verifizieren) + Playwright-Smoke**

Run (App läuft schon auf :5057; JS/CSS sind live per Browser-Reload):
```bash
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:5057")
    # Verbindungs-Tab öffnen, Oracle wählen, Dropdown togglen:
    # (konkrete Selektoren beim Umsetzen an die UI anpassen)
    pg.select_option("#conn_type", "oracle")
    pg.select_option("#cf_oracle_connect_type", "sid")
    assert pg.is_hidden("#cf_row_service_name"), "Service-Name-Feld sollte versteckt sein"
    assert pg.is_visible("#cf_row_sid"), "SID-Feld sollte sichtbar sein"
    pg.screenshot(path="scratchpad/ap70-oracle-sid.png")
    print("OK — Toggle rendert korrekt")
    b.close()
PY
```
Expected: „OK — Toggle rendert korrekt" + Screenshot zeigt SID-Feld sichtbar, Service-Name versteckt. **Screenshot ansehen** (Projekt-Konvention: hinschauen, nicht nur asserten).

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat(ap-70): Verbindungsmaske SID/Service-Umschalter (Oracle)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Release v0.68.0 + Doku

**Files:**
- Modify: `config.py`/`lucent-hub.yml` (via `sync_version.py`), Changelog EN + DE-Mirror, `luDBxP-docs/roadmap_data.py` (AP-70 → `done`), `luDBxP-docs/docs/projekt/roadmap.md` (AP-70 in „Erledigt"), `luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd` (V8 in `class … done`), icon-rail `APP_VERSION`/`TEST_COUNT`, `docs/session-kennzahlen.md` bei Bedarf.

- [ ] **Step 1: Volle Suite grün**

Run: `./venv/bin/python -m pytest`
Expected: alle PASS (459 + 6 neue = 465 passed, 11 skipped).

- [ ] **Step 2: Version bump**

Run: `./venv/bin/python sync_version.py --minor`
Expected: `config.APP_VERSION` → `0.68.0`, `lucent-hub.yml` synchron.

- [ ] **Step 3: Doku nachziehen** — Changelog EN + DE-Mirror-Eintrag v0.68.0 (AP-70); Roadmap AP-70 von `open`→`done` in `roadmap_data.py` (Datum 2026-07-02) + Prosa aus „Offene" nach „Erledigte Arbeitspakete" verschieben + `.mmd` V8 nach `class … done`; Swimlane- + Board-SVG neu rendern (`tools/generate_roadmap_svg.py`, `tools/render_mermaid.sh entwicklung-arbeitspakete`); icon-rail `APP_VERSION='0.68.0'` + `TEST_COUNT` aktualisieren; kennzahlen bei Bedarf.

- [ ] **Step 4: Whole-Branch-Review (opus)** — nie weglassen. Reviewfunde adressieren.

- [ ] **Step 5: Commit + Merge**

```bash
git add -A
git commit -m "release: v0.68.0 — AP-70 Oracle SID/Service-Verbindung

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Danach nach `master` mergen (per finishing-a-development-branch), Site + gh-pages deployen.

---

## Self-Review (gegen Spec)

- **Spec-Coverage:** build_url SID-Pfad ✅ Task 1 · Service-Default/rückwärtskompatibel ✅ Task 1 · deutsche Fehler ✅ Task 1 · Whitelist-Persistenz ✅ Task 2 · Dropdown-Maske (beide Felder, display:none) ✅ Task 3 · formParams ✅ Task 3 · DSN-Assertion gegen ?sid=-Regression ✅ Task 1 · kein init_oracle_client ✅ (Global Constraints, nirgends eingebaut) · Release/minor ✅ Task 4.
- **Placeholder-Scan:** Playwright-Selektoren in Task 3/Step 4 als „an UI anpassen" markiert — das ist der einzige bewusst offene Punkt (die konkreten DOM-Selektoren fürs Öffnen des Verbindungs-Tabs hängen an der realen UI und werden beim Umsetzen fixiert); Feld-IDs (`#cf_oracle_connect_type`, `#cf_row_sid`) sind exakt definiert.
- **Typ-Konsistenz:** `oracle_connect_type`/`sid` identisch in build_url (Task 1), Whitelist (Task 2), formParams + Feld-IDs (Task 3). `cf_row_service_name`/`cf_row_sid` konsistent zwischen `connFieldsHtml` und `renderConnFields`.
