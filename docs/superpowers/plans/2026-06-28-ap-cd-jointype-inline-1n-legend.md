# AP-C + AP-D — Join-Typ inline + 1-N-Erklärung in die Graph-Legende Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the per-step join-type dropdowns inline into the active candidate-path row (removing the separate `#sb_join_types` row) and move the 1-N/N-1 fan-out explanation from the builder's hint tile into the existing graph legend.

**Architecture:** Frontend-only. `renderPathSeq(p, isActive)` renders the active path with compact inline join-type `<select>`s; a shared `_renderPathList()` re-renders the candidate list (active row interactive, others as clickable links) and a `_wireActiveJoinTypes()` wires the active selects + orphan hints. The `#sb_join_types` and `#sb_fanout_hint` elements are removed; the static graph legend in `index.html` gains the fan-out explanation. No backend/SQL/test change.

**Tech Stack:** vanilla JS, CSS, HTML template, pytest (regression guard only).

## Global Constraints

- **Frontend-only:** edits in `web/static/js/app.js`, `web/static/css/app.css`, `web/templates/index.html`. No `web/routes.py`/`core/`/tests; generated SQL unchanged; `SB_JOIN_TYPES`/`runBuild`/orphan logic stay functionally identical (only render location changes).
- **No CDN.** Language: German user-facing copy + commit messages.
- **Tests:** `./venv/bin/python -m pytest`. Baseline **308 passed, 2 skipped** — must stay exactly that (regression guard; no Python touched).
- **Active-path-only selects:** the interactive join-type `<select>` appears only on the active path; other candidate paths render read-only (direction chips only). The select must NOT sit inside the clickable `<a>` (it would swallow clicks) — the active row uses a non-anchor wrapper.
- **Keep:** the inline 1-N/N-1 direction chips in path rows; the `· ⚠ 1-N` status in `renderJoinResult`; the AP-47 orphan hints (ported to the inline selects).
- **Compact select:** `.sb-jt` ≤ surrounding font size (clearly smaller than a normal form control).
- **Version:** patch bump 0.43.3 → 0.43.4 via `./venv/bin/python sync_version.py --patch`.

---

## Task 1: AP-C + AP-D frontend

**Files:**
- Modify: `web/static/js/app.js` (`openSqlBuilder` markup; `renderPathSeq` ~`1065`; the path-list build in `runBuild` ~`1109-1136`; `renderJoinResult` ~`998-1002`; `renderJoinTypeControls` ~`829`; `_applyOrphanHints` ~`866`), `web/static/css/app.css` (`.sb-join-types`/`.jt-lbl`/`.sb-fanout-hint`/`.jt-step` ~`299-320`; add `.sb-jt`), `web/templates/index.html` (`#graph_legend` ~`60-65`)
- Test: none added (no JS harness; verified by `node --check` + pytest regression guard + controller browser smoke).

**Interfaces:**
- Consumes: existing `SB_JOIN_TYPES`, `SB_JOIN_OPTS`, `SB_LAST`, `SB_PATH_IDX`, `_loadOrphans`, `_markActivePath`, `runBuild`, `esc`/`escAttr`.
- Produces: `renderPathSeq(p, isActive)`, `_renderPathList()`, `_wireActiveJoinTypes()`; `#sb_join_types` and `#sb_fanout_hint` removed.

- [ ] **Step 1: Remove the `#sb_join_types` and `#sb_fanout_hint` markup (`openSqlBuilder`)**

In `web/static/js/app.js`, delete these two lines from the `panel.innerHTML` template:

```javascript
    `<div class="sb-fanout-hint" id="sb_fanout_hint"></div>` +
```
and
```javascript
    `<div class="row sb-join-types" id="sb_join_types"></div>` +
```

(Leave everything else — `#path_list`, the `sql-wrap`, etc. — in place.)

- [ ] **Step 2: Rewrite `renderPathSeq` to take an `isActive` flag**

Replace the existing `renderPathSeq`:

```javascript
function renderPathSeq(p) {
  if (!p.steps || !p.steps.length) return p.tables.map(esc).join(" → ");
  let html = esc(p.steps[0].left);
  for (const s of p.steps) {
    const cls = s.to_many ? "step-dir many" : "step-dir one";
    const lbl = s.to_many ? "1-N" : "N-1";
    const tip = s.to_many
      ? "1-N (absteigend) — kann Zeilen vervielfachen"
      : "N-1 (aufsteigend) — sicher";
    html += ` <span class="${cls}" title="${tip}">${lbl}</span> ${esc(s.right)}`;
  }
  return html;
}
```

with (active path gains a compact join-type select + orphan span per step):

```javascript
function renderPathSeq(p, isActive) {
  if (!p.steps || !p.steps.length) return p.tables.map(esc).join(" → ");
  let html = esc(p.steps[0].left);
  p.steps.forEach((s, k) => {
    const cls = s.to_many ? "step-dir many" : "step-dir one";
    const lbl = s.to_many ? "1-N" : "N-1";
    const tip = s.to_many
      ? "1-N (absteigend) — kann Zeilen vervielfachen"
      : "N-1 (aufsteigend) — sicher";
    html += ` <span class="${cls}" title="${tip}">${lbl}</span>`;
    if (isActive) {
      const cur = (SB_JOIN_TYPES[k] || "INNER").toUpperCase();
      const opts = SB_JOIN_OPTS.map((o) =>
        `<option${o === cur ? " selected" : ""}>${o}</option>`).join("");
      html += ` <select class="sb-jt" data-step="${k}" ` +
              `title="${escAttr(s.left)} → ${escAttr(s.right)}">${opts}</select>` +
              `<span class="jt-orphan" data-step="${k}"></span>`;
    }
    html += ` ${esc(s.right)}`;
  });
  return html;
}
```

- [ ] **Step 3: Add `_renderPathList()` and `_wireActiveJoinTypes()`; retarget orphan hints**

In `web/static/js/app.js`, add these two functions (place them just above `renderJoinResult`):

```javascript
// Render the candidate-path list. The active path is interactive (inline
// join-type selects); the others are clickable links that switch the active
// path. Re-rendered whenever the active index changes (so selects follow it).
function _renderPathList() {
  const list = $("path_list");
  if (!list || !SB_LAST) return;
  list.innerHTML = SB_LAST.paths.map((p, i) => {
    const active = i === SB_PATH_IDX;
    const seq = renderPathSeq(p, active);
    const inner = active
      ? `<span class="path-seq">${seq}</span>`
      : `<a href="#" data-i="${i}">${seq}</a>`;
    return `<li data-i="${i}"><span class="path-mark"></span>${inner}</li>`;
  }).join("");
  list.querySelectorAll("a").forEach((a) =>
    a.addEventListener("click", (ev) => { ev.preventDefault(); renderJoinResult(+a.dataset.i); }));
  _markActivePath();
  _wireActiveJoinTypes();
}

// Wire the active path's inline join-type selects to SB_JOIN_TYPES + rebuild,
// and load/apply the AP-47 orphan hints onto them.
function _wireActiveJoinTypes() {
  const list = $("path_list");
  if (!list) return;
  list.querySelectorAll(".path-seq .sb-jt").forEach((sel) =>
    sel.addEventListener("change", () => {
      SB_JOIN_TYPES[+sel.dataset.step] = sel.value;
      runBuild(true);
    }));
  _loadOrphans(SB_PATH_IDX).then(() => _applyOrphanHints(SB_PATH_IDX));
}
```

Then change `_applyOrphanHints` to target the active path's sequence span instead of the removed `#sb_join_types` box — replace its first lines:

```javascript
function _applyOrphanHints(i) {
  const flags = SB_ORPHANS_CACHE[_orphanKey(i)];
  const box = $("sb_join_types");
  if (!flags || !box) return;
```

with:

```javascript
function _applyOrphanHints(i) {
  const flags = SB_ORPHANS_CACHE[_orphanKey(i)];
  const list = $("path_list");
  const box = list ? list.querySelector(".path-seq") : null;
  if (!flags || !box) return;
```

(The rest of `_applyOrphanHints` — `box.querySelectorAll("select")` and `box.querySelectorAll(".jt-orphan")` — works unchanged against the active row.)

- [ ] **Step 4: Remove `renderJoinTypeControls`; point `renderJoinResult` at `_renderPathList`**

In `web/static/js/app.js`, delete the whole `renderJoinTypeControls` function (the `function renderJoinTypeControls(i) { … }` block, ~lines 829-852; keep the `const SB_JOIN_OPTS = …` line above it — it is still used by `renderPathSeq`).

In `renderJoinResult`, replace the two lines:

```javascript
  SB_PATH_IDX = i;
  _markActivePath();
```

with:

```javascript
  SB_PATH_IDX = i;
  _renderPathList();
```

and delete the later call `renderJoinTypeControls(i);` (was ~line 1002).

- [ ] **Step 5: Replace the path-list build + remove fanout-hint in `runBuild`**

In `runBuild`, find the block that builds the list and the fanout hint (it currently does `list.innerHTML = data.paths.map(…renderPathSeq(p)…)`, wires the `a` click handlers, calls `_markActivePath()`, then fills `$("sb_fanout_hint")`). Replace that whole block:

```javascript
    const list = $("path_list");
    // The verbose per-branch fan-out text is dropped — the inline 1-N / N-1 chips
    // already mark direction. A single compact hint tile (below) explains 1-N.
    list.innerHTML = data.paths.map((p, i) =>
      `<li data-i="${i}"><span class="path-mark"></span>` +
      `<a href="#" data-i="${i}">${renderPathSeq(p)}</a></li>`).join("");
    list.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); renderJoinResult(+a.dataset.i); }));
    _markActivePath();
    // Show the fan-out hint once if any candidate path has a descending (1-N) step.
    const hint = $("sb_fanout_hint");
    if (hint) {
      const hasFanout = data.paths.some((p) =>
        (p.steps || []).some((s) => s.to_many));
      hint.innerHTML = hasFanout
        ? `<span class="step-dir many">1-N</span> kann Zeilen vervielfachen (Fan-out)`
        : "";
    }
```

with (the inline 1-N/N-1 chips + the legend now carry the fan-out meaning, so the tile is gone):

```javascript
    _renderPathList();
```

(Note: `SB_PATH_IDX` is set just above this block in `runBuild` as today; `_renderPathList()` reads it.)

- [ ] **Step 6: Remove the `#sb_join_types` clear in the empty-path branch (`runBuild`)**

Still in `runBuild`, in the no-paths branch, delete the line:

```javascript
      if ($("sb_join_types")) $("sb_join_types").innerHTML = "";
```

- [ ] **Step 7: CSS — add `.sb-jt`, drop the dead rules (`web/static/css/app.css`)**

Add a compact inline-select rule (place near the `.step-dir` rules):

```css
/* AP-C: inline join-type select in the active path row — no larger than text. */
.sb-jt {
  font-size: .72rem; height: auto; padding: 0 1px; margin: 0 1px;
  vertical-align: baseline; line-height: 1.2;
  width: auto; min-width: 0;
}
```

Then delete the now-unused rules: `.sb-fanout-hint:empty { … }` + `.sb-fanout-hint { … }`, `.sb-join-types { … }` + `.sb-join-types:empty { … }`, and `.jt-lbl { … }` (the separate-row label is gone). Keep `.jt-orphan*` and `.step-dir*` rules. (If `.sb-jt` global width is overridden by `.sqlbuilder select { width: var(--sb-ctrl-w) … }`, the `.sb-jt` rule above must win — it is more specific by class; verify in the browser smoke that the select is compact.)

- [ ] **Step 8: Graph legend — fold the fan-out explanation into the existing entry (`web/templates/index.html`)**

The legend already has a „Join-Richtung" entry. Replace it:

```html
        <span><i class="lg-chip lg-one">N-1</i><i class="lg-chip lg-many">1-N</i>Join-Richtung</span>
```

with two explained entries:

```html
        <span><i class="lg-chip lg-many">1-N</i>vervielfacht Zeilen (Fan-out)</span>
        <span><i class="lg-chip lg-one">N-1</i>sicher</span>
```

- [ ] **Step 9: Verify syntax + suite**

Run: `node --check web/static/js/app.js` → exit 0.
Run: `grep -c "sb_join_types\|sb_fanout_hint\|renderJoinTypeControls" web/static/js/app.js` → expect `0`.
Run: `./venv/bin/python -m pytest -q` → `308 passed, 2 skipped`.

- [ ] **Step 10: Commit**

```bash
git add web/static/js/app.js web/static/css/app.css web/templates/index.html
git commit -m "feat: SQL-Builder — Join-Typ inline in aktive Pfad-Zeile + 1-N-Erklärung in Graph-Legende

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Controller browser smoke (no `#sb_join_types` row and no `#sb_fanout_hint` tile; the active path shows a COMPACT join-type select per step that rebuilds SQL on change and carries orphan hints; a non-active path shows no select; clicking another path moves the selects to it; the legend shows the 1-N/N-1 fan-out lines; no console errors) runs after this task.

---

## Task 2: Release v0.43.4 + oberflaeche doc

**Files:**
- Modify: `config.py` + `lucent-hub.yml` (via `sync_version.py`), `CHANGELOG.md` + mirror `luDBxP-docs/docs/entwicklung/changelog.md`, `luDBxP-docs/docs/javascripts/icon-rail.js` (APP_VERSION), `luDBxP-docs/docs/referenz/oberflaeche.md`, site rebuild.

**Interfaces:**
- Consumes: the UI change from Task 1.
- Produces: a v0.43.4 patch release documenting it.

- [ ] **Step 1: Bump version (patch)**

Run: `./venv/bin/python sync_version.py --patch` → `config.py` + `lucent-hub.yml` `0.43.3 → 0.43.4`.

- [ ] **Step 2: Changelog (root + mirror)**

Add to `CHANGELOG.md`:

```markdown
## [0.43.4] — 2026-06-28

### Changed
- SQL-Builder: the per-step join-type dropdowns now sit inline in the active
  candidate-path row (next to the 1-N/N-1 direction chips), so the separate
  join-type row is gone. The fan-out explanation moved from the builder hint
  tile into the schema-graph legend (1-N vervielfacht Zeilen / N-1 sicher).
  Markup/CSS only — no behavior change.
```

Add to `luDBxP-docs/docs/entwicklung/changelog.md`:

```markdown
## [0.43.4] — 2026-06-28

### Geändert
- SQL-Builder: die Join-Typ-Dropdowns sitzen jetzt inline in der aktiven
  Kandidatenpfad-Zeile (neben den 1-N/N-1-Richtungs-Chips), die separate
  Join-Typ-Zeile entfällt. Die Fan-out-Erklärung wanderte aus der Builder-
  Hinweiskachel in die Schema-Graph-Legende (1-N vervielfacht Zeilen / N-1
  sicher). Nur Markup/CSS — keine Verhaltensänderung.
```

- [ ] **Step 3: Bump icon-rail APP_VERSION**

In `luDBxP-docs/docs/javascripts/icon-rail.js`, set `APP_VERSION` to `'0.43.4'`; leave `TEST_COUNT` at `'308'`.

- [ ] **Step 4: Update the UI reference page**

In `luDBxP-docs/docs/referenz/oberflaeche.md`, update the SQL-Builder description: join-type selection is now inline per step in the active path (no separate row); the 1-N/N-1 fan-out meaning is explained in the graph legend (and the builder no longer shows a separate fan-out tile). Concise + factual.

- [ ] **Step 5: Build site + verify**

Run: `cd luDBxP-docs && ./run_luDBxP_docs.sh --build` → builds, no errors.
Run: `grep -o "APP_VERSION *= *'0.43.4'" site/javascripts/icon-rail.js` → match.
Run: `grep -o "0.43.4" site/entwicklung/changelog/index.html | head -1` → `0.43.4`.
Then from repo root: `./venv/bin/python -m pytest -q` → `308 passed, 2 skipped`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: Release v0.43.4 — Join-Typ inline + 1-N-Erklärung in Graph-Legende

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> Push + gh-pages deploy is a separate user-confirmed step.

---

## Self-Review

**Spec coverage:**
- AP-C: `#sb_join_types` row removed → Task 1 Step 1; inline select on active path → Steps 2-3; rewire + orphan port → Steps 3-4; compact CSS → Step 7; old CSS removed → Step 7. ✓
- AP-D: `#sb_fanout_hint` removed (markup Step 1, fill Step 5, CSS Step 7); legend explanation → Step 8. ✓
- Selects active-path-only, not inside `<a>` → Step 3 `_renderPathList` (active → `path-seq` span, others → `<a>`). ✓
- Keep direction chips + result `· ⚠ 1-N` (untouched) + orphan hints (Step 3). ✓
- No backend/test; suite 308/2 → Task 1 Step 9, Task 2 Step 5. ✓
- Patch 0.43.3→0.43.4 + changelog + badge + oberflaeche + site → Task 2. ✓
- Browser smoke (controller) → after Task 1. ✓

**Placeholder scan:** No TBD/TODO; every step shows exact code/commands. ✓

**Type consistency:** `renderPathSeq(p, isActive)`, `_renderPathList()`, `_wireActiveJoinTypes()`, `.sb-jt`/`.path-seq`/`.jt-orphan` classes, `SB_JOIN_TYPES`/`SB_JOIN_OPTS`/`SB_PATH_IDX` — consistent across steps; `_applyOrphanHints` retarget matches the `.path-seq` wrapper from `_renderPathList`. ✓
