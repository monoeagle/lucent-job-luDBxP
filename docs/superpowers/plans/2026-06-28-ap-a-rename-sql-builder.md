# AP-A — Umbenennung „Join-Builder" → „SQL-Builder" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the builder tool from „Join-Builder" to „SQL-Builder" throughout the frontend (visible text + every internal identifier) and the user-facing docs.

**Architecture:** A purely mechanical rename. The frontend lives in one file (`web/static/js/app.js`) plus its stylesheet (`web/static/css/app.css`); a deterministic set of search-replace substitutions plus three visible-string swaps does the whole code rename, verified by a "zero leftover" grep, a JS syntax check, and a browser smoke test. Docs are renamed in current/forward-facing pages only (historical changelog stays). No backend, no API, no behavior change.

**Tech Stack:** vanilla JS, CSS, Markdown, Mermaid, pytest (regression guard only).

## Global Constraints

- **No backend change:** `web/routes.py` and the API endpoint `/api/joinpath` are NOT renamed („joinpath" ≠ „joinbuilder"). No Python is touched.
- **No behavior/layout change:** identifiers and labels only.
- **Language:** German user-facing copy and commit messages. Button label is exactly **„Generieren"**; visible tool name is exactly **„SQL-Builder"**.
- **No CDN:** no new external assets (none needed).
- **Tests:** `./venv/bin/python -m pytest`. Baseline **308 passed, 2 skipped** — must stay exactly that (no test references the name; the suite is a regression guard only).
- **Identifier mapping (verbatim):** `JoinBuilder`→`SqlBuilder`, `joinbuilder`→`sqlbuilder`, `JB_`→`SB_`, `jb_`→`sb_`, `jb-`→`sb-`. Visible: „Join-Builder"→„SQL-Builder", „Join-Pfad bauen"→„Generieren".
- **Leftover check (binding):** after the code rename, `grep -nE 'jb[-_]|JB_|JoinBuilder|joinbuilder' web/static/js/app.js web/static/css/app.css` MUST print nothing.
- **Docs exclude (historical record — do NOT rename):** `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/_data/project-activity.json`, and `luDBxP-docs/mermaid-sources/referenz-architektur-archiv-1.mmd`.
- **Version:** patch bump 0.43.1 → 0.43.2 via `./venv/bin/python sync_version.py --patch` (never edit `config.APP_VERSION` by hand).

---

## Task 1: Code rename — `app.js` + `app.css`

**Files:**
- Modify: `web/static/js/app.js`, `web/static/css/app.css`
- Test: none added (no JS unit harness; verified by grep + `node --check` + the existing pytest suite as a regression guard + a controller browser smoke afterwards).

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the frontend now uses `SqlBuilder`/`sqlbuilder`/`SB_`/`sb_`/`sb-` identifiers and shows „SQL-Builder" / „Generieren". Task 2 (docs) and the release reference the new visible name.

- [ ] **Step 1: Snapshot the leftover-grep BEFORE (should be non-empty)**

Run: `grep -cE 'jb[-_]|JB_|JoinBuilder|joinbuilder' web/static/js/app.js web/static/css/app.css`
Expected: non-zero counts (e.g. app.js large, app.css ~13) — confirms there is something to rename.

- [ ] **Step 2: Apply the identifier substitutions to `app.js`**

Run (order is safe — the five patterns do not overlap):

```bash
perl -pi -e 's/JoinBuilder/SqlBuilder/g; s/joinbuilder/sqlbuilder/g; s/JB_/SB_/g; s/jb_/sb_/g; s/jb-/sb-/g;' web/static/js/app.js
```

- [ ] **Step 3: Apply the visible-string substitutions to `app.js`**

The hyphenated visible string „Join-Builder" is untouched by Step 2 (it is not the identifier „JoinBuilder"). Swap the two visible labels:

```bash
perl -pi -e 's/Join-Builder/SQL-Builder/g; s/Join-Pfad bauen/Generieren/g;' web/static/js/app.js
```

- [ ] **Step 4: Apply the class substitution to `app.css`**

`app.css` contains only `jb-*` class rules:

```bash
perl -pi -e 's/jb-/sb-/g;' web/static/css/app.css
```

- [ ] **Step 5: Verify zero leftovers (binding)**

Run: `grep -nE 'jb[-_]|JB_|JoinBuilder|joinbuilder' web/static/js/app.js web/static/css/app.css`
Expected: NO output (empty). If anything prints, rename it and re-run until empty.

- [ ] **Step 6: Verify JS syntax**

Run: `node --check web/static/js/app.js`
Expected: exit 0, no output.

- [ ] **Step 7: Confirm the visible labels are present**

Run: `grep -nE 'SQL-Builder|Generieren' web/static/js/app.js`
Expected: at least the menu entry, the tab title (`ensureTab("sqlbuilder", "SQL-Builder", …)`), and the build button (`>Generieren<`).

- [ ] **Step 8: Run the full suite (regression guard)**

Run: `./venv/bin/python -m pytest -q`
Expected: `308 passed, 2 skipped` (unchanged — no Python touched).

- [ ] **Step 9: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css
git commit -m "refactor: SQL-Builder — Join-Builder/jb-/JB_ durchgängig umbenannt (UI + Bezeichner)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Controller browser smoke (open the **SQL-Builder** tab, connect to the demo DB, click **Generieren** → a path + SQL render, no console errors, styling intact because the `sb-*` classes match) runs after this task, not in the implementer.

---

## Task 2: Docs rename + Release v0.43.2

**Files:**
- Modify: current/forward-facing docs (see Step 1), `luDBxP-docs/mermaid-sources/*.mmd` (except the archiv source), `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` + mirror (new entry only), `luDBxP-docs/docs/javascripts/icon-rail.js` (APP_VERSION), site rebuild.

**Interfaces:**
- Consumes: the new visible name „SQL-Builder" established in Task 1.
- Produces: a v0.43.2 patch release documenting the rename.

- [ ] **Step 1: Rename „Join-Builder" → „SQL-Builder" in current/forward-facing docs**

Apply to these files (all currently contain „Join-Builder"), EXCLUDING the historical record:

```bash
for f in CLAUDE.md \
  luDBxP-docs/docs/referenz/oberflaeche.md \
  luDBxP-docs/docs/referenz/architektur.md \
  luDBxP-docs/docs/referenz/fanout-warnung.md \
  luDBxP-docs/docs/referenz/outer-joins.md \
  luDBxP-docs/docs/referenz/usecases.md \
  luDBxP-docs/docs/grundlagen/schnellstart.md \
  luDBxP-docs/docs/entwicklung/testing.md \
  luDBxP-docs/docs/entwicklung/projektstruktur.md \
  luDBxP-docs/docs/projekt/roadmap.md \
  luDBxP-docs/mermaid-sources/projekt-roadmap-1.mmd \
  luDBxP-docs/mermaid-sources/referenz-architektur-3.mmd \
  luDBxP-docs/mermaid-sources/entwicklung-arbeitspakete-1.mmd ; do
  perl -pi -e 's/Join-Builder/SQL-Builder/g;' "$f"
done
```

Do NOT touch: `CHANGELOG.md`, `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/_data/project-activity.json`, `luDBxP-docs/mermaid-sources/referenz-architektur-archiv-1.mmd` (historical/archived). Note: the generated `luDBxP-docs/docs/entwicklung/changelog.md` mirror is regenerated/edited only in Step 4.

- [ ] **Step 2: Verify the exclude held**

Run: `grep -l 'Join-Builder' CHANGELOG.md luDBxP-docs/docs/entwicklung/changelog.md luDBxP-docs/mermaid-sources/referenz-architektur-archiv-1.mmd`
Expected: these three still contain „Join-Builder" (historical record preserved). And:
Run: `grep -rl 'Join-Builder' luDBxP-docs/docs/referenz/ CLAUDE.md`
Expected: no output (current reference pages fully renamed).

- [ ] **Step 3: Bump the version (patch)**

Run: `./venv/bin/python sync_version.py --patch`
Expected: `config.py` + `lucent-hub.yml` go `0.43.1 → 0.43.2`.

- [ ] **Step 4: Add the changelog entry (root + mirror)**

Add a `[0.43.2] — 2026-06-28` section to `CHANGELOG.md` and the mirror `luDBxP-docs/docs/entwicklung/changelog.md`:

Root (English):
```markdown
## [0.43.2] — 2026-06-28

### Changed
- Renamed the builder from „Join-Builder" to „SQL-Builder" across the UI
  (menu, tab, build button now „Generieren") and the current documentation.
  Internal identifiers were renamed in lockstep (`jb-`→`sb-`, `jb_`→`sb_`,
  `JB_`→`SB_`, `joinbuilder`→`sqlbuilder`). No behavior change; the
  `/api/joinpath` endpoint is unchanged.
```

Mirror (German):
```markdown
## [0.43.2] — 2026-06-28

### Geändert
- Builder von „Join-Builder" in „SQL-Builder" umbenannt — UI (Menü, Tab,
  Bau-Button heißt jetzt „Generieren") und aktuelle Doku. Interne Bezeichner
  im Gleichschritt umbenannt (`jb-`→`sb-`, `jb_`→`sb_`, `JB_`→`SB_`,
  `joinbuilder`→`sqlbuilder`). Keine Verhaltensänderung; der Endpoint
  `/api/joinpath` bleibt unverändert.
```

- [ ] **Step 5: Bump icon-rail APP_VERSION (TEST_COUNT unchanged)**

In `luDBxP-docs/docs/javascripts/icon-rail.js`, change `APP_VERSION` from `'0.43.1'` to `'0.43.2'`. Leave `TEST_COUNT` at `'308'` (no test change).

- [ ] **Step 6: Build the site and verify**

Run: `cd luDBxP-docs && ./run_luDBxP_docs.sh --build`
Expected: mermaid SVGs regenerate, site builds, no errors. Then:
Run: `grep -o "SQL-Builder" site/referenz/oberflaeche/index.html | head -1` → expect `SQL-Builder`.
Run: `grep -o "APP_VERSION *= *'0.43.2'" site/javascripts/icon-rail.js` → expect a match.
Then re-run `./venv/bin/python -m pytest -q` from the repo root → still `308 passed, 2 skipped`.

- [ ] **Step 7: Commit the release**

```bash
git add -A
git commit -m "docs: Release v0.43.2 — Join-Builder in SQL-Builder umbenannt (Doku/Changelog/Site)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Pushing to `origin/master` and the `gh-pages` deploy are a separate, user-confirmed step — do not push without confirmation.

---

## Self-Review

**Spec coverage:**
- Visible text (menu/tab „SQL-Builder", button „Generieren") → Task 1 Steps 3, 7. ✓
- Internal identifiers (`JoinBuilder`/`joinbuilder`/`JB_`/`jb_`/`jb-`) in app.js + app.css → Task 1 Steps 2-5 + binding leftover grep. ✓
- API endpoint `/api/joinpath` / `web/routes.py` untouched → Global Constraints; no task edits them. ✓
- Docs renamed (current/forward-facing) → Task 2 Step 1; exclude list (changelog root+mirror, project-activity, archiv mmd) → Step 1 + verified Step 2. ✓
- Architektur mermaid renamed + regenerated → Task 2 Step 1 (referenz-architektur-3.mmd) + Step 6 build. ✓
- No Python/test impact, suite stays 308/2 → Task 1 Step 8, Task 2 Step 6. ✓
- Patch bump 0.43.1→0.43.2 + changelog + badge version + site → Task 2 Steps 3-6. ✓
- Browser smoke (controller) → noted after Task 1. ✓

**Placeholder scan:** No TBD/TODO; every step has the exact command or text. ✓

**Type consistency:** mapping strings identical across Global Constraints, Task 1 substitutions, and the changelog text (`jb-`→`sb-`, `jb_`→`sb_`, `JB_`→`SB_`, `joinbuilder`→`sqlbuilder`, button „Generieren", name „SQL-Builder"). ✓
