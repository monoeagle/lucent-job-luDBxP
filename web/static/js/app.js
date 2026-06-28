"use strict";

let SCHEMA = { tables: [], views: [] };
let CY = null;  // Cytoscape instance for the schema graph
let SAVED_CONNS = [];  // saved connections (without passwords)
let SELECTED_SCHEMA = "";  // empty = default schema
const OPERATORS = ["=", "!=", "<", ">", "<=", ">=", "LIKE",
                   "IS NULL", "IS NOT NULL", "IN", "BETWEEN"];
const DB_TYPES = [
  { v: "sqlite", label: "SQLite (Datei)" },
  { v: "postgresql", label: "PostgreSQL" },
  { v: "mysql", label: "MySQL / MariaDB" },
  { v: "mssql", label: "MS SQL Server" },
  { v: "oracle", label: "Oracle" },
];
const PORT_DEFAULTS = { postgresql: 5432, mysql: 3306, mssql: 1433, oracle: 1521 };

// ===== Graph selection state (AP-1: interactive join-path selection) =====
let GRAPH_SEL = { source: null, target: null };

// Padding (px) around the graph's bounding box on fit — small so the graph
// fills the panel and stays centered after layout/resize.
const GRAPH_FIT_PAD = 16;

// ===== SQL-Builder state (AP-6: result refresh + row-count selection) =====
let SB_LAST = null;     // { body, paths } from the last successful build
let SB_PATH_IDX = 0;    // currently selected path index
let SB_JOIN_TYPES = []; // AP-41: per-step join type for the active path (INNER default)

const $ = (id) => document.getElementById(id);

// The real URL (with password) lives in a hidden field; show a masked form.
function maskUrl(url) {
  return url.replace(/(:\/\/[^:/@]+:)[^@]*@/, "$1***@");
}
function setCurrentUrl(url) {
  $("connection_url").value = url;
  const cc = $("current_conn");           // optional (removed from the topbar)
  if (cc) cc.textContent = url ? maskUrl(url) : "(keine Verbindung)";
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function escAttr(s) { return esc(s).replace(/"/g, "&quot;"); }

async function postJSON(url, body) {
  // Auto-inject selected schema into every request that carries a connection_url
  if (SELECTED_SCHEMA && body && body.connection_url !== undefined
      && body.schema === undefined) {
    body = { ...body, schema: SELECTED_SCHEMA };
  }
  let r;
  try {
    r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    // fetch() throws a TypeError ("Failed to fetch") only when the server is
    // unreachable — translate it into an actionable message.
    throw new Error(
      "Server nicht erreichbar — läuft LucentTools DB Explorer? " +
      "Starte die App mit „bash run.sh“ und lade die Seite neu.");
  }
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || "Fehler");
  return data;
}

function connUrl() { return $("connection_url").value; }
function includeImplied() { return $("include_implied").checked; }
function tableByName(name) { return SCHEMA.tables.find((t) => t.name === name); }
function optionList(names) { return names.map((n) => `<option>${n}</option>`).join(""); }

// Aggregate options. value = token sent in the request; label = shown to the user.
// COUNT* renders COUNT(*) (column ignored); "COUNT DISTINCT" renders COUNT(DISTINCT col).
const AGG_OPTIONS = [
  { v: "COUNT", l: "COUNT" },
  { v: "COUNT*", l: "COUNT(*)" },
  { v: "COUNT DISTINCT", l: "COUNT(DISTINCT)" },
  { v: "SUM", l: "SUM" },
  { v: "AVG", l: "AVG" },
  { v: "MIN", l: "MIN" },
  { v: "MAX", l: "MAX" },
];
function aggOptionTags() {
  return AGG_OPTIONS.map((o) => `<option value="${o.v}">${o.l}</option>`).join("");
}
function aggOptions() {              // SELECT/ORDER BY: optional aggregate ("—" first)
  return `<option value="">—</option>` + aggOptionTags();
}

// COUNT(*) ignores the column — disable the paired column <select> when chosen
// (its value is still submitted and ignored server-side). Other aggregates keep it.
function wireAggColDisable(aggSel, colSel) {
  if (!aggSel || !colSel) return;
  const sync = () => { colSel.disabled = (aggSel.value === "COUNT*"); };
  aggSel.addEventListener("change", sync);
  sync();
}

// Aggregat-Ops: scalar comparison operators allowed in a HAVING row.
const HAVING_OPS = ["=", "!=", "<", ">", "<=", ">="];

// ===== Tabs =====
function activateTab(id) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === id));
  document.querySelectorAll(".panel").forEach((p) =>
    p.classList.toggle("active", p.dataset.tab === id));
}

function closeTab(id) {
  const tab = document.querySelector(`.tab[data-tab="${id}"]`);
  const panel = document.querySelector(`.panel[data-tab="${id}"]`);
  const wasActive = tab && tab.classList.contains("active");
  if (tab) tab.remove();
  if (panel) panel.remove();
  if (wasActive) {
    const first = document.querySelector(".tab");
    if (first) activateTab(first.dataset.tab);
  }
}

// Returns the panel element (existing or freshly created), and activates it.
function ensureTab(id, title, closable) {
  let panel = document.querySelector(`.panel[data-tab="${id}"]`);
  if (panel) { activateTab(id); return panel; }

  const tab = document.createElement("button");
  tab.className = "tab";
  tab.dataset.tab = id;
  tab.innerHTML = `<span class="t-title"></span>` +
    (closable ? `<span class="close">✕</span>` : "");
  tab.querySelector(".t-title").textContent = title;
  tab.addEventListener("click", (ev) => {
    if (ev.target.classList.contains("close")) closeTab(id);
    else activateTab(id);
  });
  $("tabbar").appendChild(tab);

  panel = document.createElement("div");
  panel.className = "panel";
  panel.dataset.tab = id;
  $("tabpanels").appendChild(panel);
  activateTab(id);
  return panel;
}

// ===== Object browser (sidebar) =====
function renderSidebar() {
  const objList = (items, kind) => items.map((o) =>
    `<li data-kind="${kind}" data-name="${esc(o.name)}">${esc(o.name)}</li>`).join("");
  $("objects").innerHTML =
    `<h3>Tools</h3><ul class="objlist">` +
    `<li data-action="connections">Verbindungen</li>` +
    `<li data-action="sqlbuilder">SQL-Builder</li>` +
    `<li data-action="analyzer">SQL-Analyzer</li></ul>` +
    `<h3>Tabellen (${SCHEMA.tables.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.tables, "table")}</ul>` +
    `<h3>Views (${SCHEMA.views.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.views, "view")}</ul>` +
    `<div class="sidebar-bottom"><h3>Info</h3>` +
    `<ul class="objlist"><li data-action="info">Übersicht</li></ul></div>`;
  $("objects").querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", () => {
      if (li.dataset.action === "sqlbuilder") openSqlBuilder();
      else if (li.dataset.action === "analyzer") openAnalyzer();
      else if (li.dataset.action === "connections") openConnections();
      else if (li.dataset.action === "info") openInfo();
      else openDetail(li.dataset.kind, li.dataset.name);
    });
  });
  applyObjectFilter();  // re-apply any active search filter to the rebuilt list
}

// AP-13: filter the table/view lists in the object browser by name.
function applyObjectFilter() {
  const inp = $("obj_search");
  if (!inp) return;
  const q = inp.value.trim().toLowerCase();
  $("objects").querySelectorAll("li[data-name]").forEach((li) => {
    li.style.display = li.dataset.name.toLowerCase().includes(q) ? "" : "none";
  });
}

function setupObjectSearch() {
  const inp = $("obj_search");
  if (inp) inp.addEventListener("input", applyObjectFilter);
}

// ===== Info tab =====
async function openInfo() {
  const panel = ensureTab("info", "Info", true);
  panel.innerHTML = "<div class='detail'><h2>Info</h2><p class='hint'>lädt…</p></div>";

  let meta = null;
  try {
    const r = await fetch("/api/info");
    if (r.ok) meta = await r.json();
  } catch (e) { /* offline metadata fallback below */ }

  const stackRows = meta
    ? meta.stack.map((s) =>
        `<tr><td>${esc(s.name)}</td><td>${esc(s.version)}</td></tr>`).join("")
    : "";
  const fkCount = SCHEMA.tables.reduce((n, t) => n + t.foreign_keys.length, 0);
  const dbBlock = SCHEMA.tables.length
    ? `<h3>Verbindung</h3><table class="cols"><tbody>` +
      `<tr><td>Connection-URL</td><td>${esc(connUrl())}</td></tr>` +
      `<tr><td>Tabellen</td><td>${SCHEMA.tables.length}</td></tr>` +
      `<tr><td>Views</td><td>${SCHEMA.views.length}</td></tr>` +
      `<tr><td>Deklarierte Foreign Keys</td><td>${fkCount}</td></tr>` +
      `</tbody></table>`
    : "<p class='hint'>Noch nicht mit einer Datenbank verbunden.</p>";

  panel.innerHTML =
    `<div class="detail">` +
    `<h2>${esc(meta ? meta.name : "LucentTools DB Explorer")}</h2>` +
    `<table class="cols"><tbody>` +
    `<tr><td>Version</td><td>${esc(meta ? meta.version : "?")}</td></tr>` +
    `<tr><td>Ersteller</td><td>${esc(meta ? meta.author : "?")}</td></tr>` +
    `</tbody></table>` +
    `<h3>Technologie-Stack</h3>` +
    `<table class="cols"><thead><tr><th>Komponente</th><th>Version</th></tr></thead>` +
    `<tbody>${stackRows}</tbody></table>` +
    dbBlock +
    `<p class="hint">Implizite (geratene) Foreign Keys lassen sich über die ` +
    `Checkbox oben einschalten.</p></div>`;
}

// ===== Detail tab (table or view) with sub-tabs =====
function colRows(columns, withPk) {
  return columns.map((c) => {
    const pk = withPk && c.pk ? ` <span class="badge">PK</span>` : "";
    const tip = c.comment ? ` title="${escAttr(c.comment)}"` : "";
    return `<tr${tip}><td>${esc(c.name)}${pk}</td><td>${esc(c.type)}</td></tr>`;
  }).join("");
}

async function loadData(name, container) {
  container.innerHTML = "<p class='hint'>lädt…</p>";
  try {
    const d = await postJSON("/api/data", { connection_url: connUrl(), object: name });
    if (!d.rows.length) { container.innerHTML = "<p class='hint'>keine Zeilen</p>"; return; }
    const head = d.columns.map((c) => `<th>${esc(c)}</th>`).join("");
    const body = d.rows.map((r) =>
      "<tr>" + r.map((v) =>
        `<td>${v === null ? "<i>NULL</i>" : esc(v)}</td>`).join("") + "</tr>").join("");
    container.innerHTML =
      `<table class="cols"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  } catch (e) {
    container.innerHTML = `<p class='hint'>Fehler: ${esc(e.message)}</p>`;
  }
}

function openDetail(kind, name) {
  const id = `det:${kind}:${name}`;
  const panel = ensureTab(id, name, true);
  if (panel.dataset.built) return;
  panel.dataset.built = "1";

  let defHtml, sqlText;
  if (kind === "table") {
    const t = tableByName(name);
    const fks = t.foreign_keys.length
      ? "<ul>" + t.foreign_keys.map((f) =>
          `<li>${esc(f.columns.join(", "))} → ${esc(f.ref_table)}.${esc(f.ref_columns.join(", "))}</li>`).join("") + "</ul>"
      : "<p class='hint'>keine Foreign Keys</p>";
    defHtml = `<h2${t.comment ? ` title="${escAttr(t.comment)}"` : ""}>Tabelle: ${esc(t.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(t.columns, true)}</tbody></table>` +
      `<h3>Foreign Keys</h3>${fks}`;
    sqlText = t.ddl;
  } else {
    const v = SCHEMA.views.find((x) => x.name === name);
    defHtml = `<h2>View: ${esc(v.name)}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(v.columns, false)}</tbody></table>`;
    sqlText = v.definition;
  }

  panel.innerHTML =
    `<div class="detail">` +
    `<div class="subtabbar">` +
    `<button class="subtab active" data-sub="def">Definition</button>` +
    `<button class="subtab" data-sub="data">Daten</button>` +
    `<button class="subtab" data-sub="sql">SQL</button></div>` +
    `<div class="subpanel active" data-sub="def">${defHtml}</div>` +
    `<div class="subpanel" data-sub="data"></div>` +
    `<div class="subpanel" data-sub="sql"><pre class="viewdef"></pre></div></div>`;
  panel.querySelector('.subpanel[data-sub="sql"] .viewdef').textContent =
    sqlText || "(keine Definition)";

  const dataPanel = panel.querySelector('.subpanel[data-sub="data"]');
  let dataLoaded = false;
  panel.querySelectorAll(".subtab").forEach((st) => {
    st.addEventListener("click", () => {
      panel.querySelectorAll(".subtab").forEach((x) =>
        x.classList.toggle("active", x === st));
      panel.querySelectorAll(".subpanel").forEach((p) =>
        p.classList.toggle("active", p.dataset.sub === st.dataset.sub));
      if (st.dataset.sub === "data" && !dataLoaded) {
        dataLoaded = true;
        loadData(name, dataPanel);
      }
    });
  });
}

// ===== SQL-Builder tab =====
function openSqlBuilder() {
  const panel = ensureTab("sqlbuilder", "SQL-Builder", true);
  if (panel.dataset.built) return;
  panel.dataset.built = "1";
  panel.innerHTML =
    `<div class="sqlbuilder">` +
    `<div class="row"><label>Start</label>` +
    `<select id="start_table"></select> . <select id="start_col"></select>` +
    `<select id="start_agg" class="sb-agg" title="Aggregatfunktion">${aggOptions()}</select></div>` +
    `<div class="row"><label>Ziel</label>` +
    `<select id="target_table"></select> . <select id="target_col"></select>` +
    `<select id="target_agg" class="sb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button id="btn_swap" class="sb-swap" type="button" title="Start und Ziel vertauschen" ` +
    `aria-label="Start und Ziel vertauschen">⇅</button></div>` +
    `<div class="filters" id="filters"></div>` +
    `<div class="filters" id="order_bys"></div>` +
    `<div class="filters" id="extra_cols"></div>` +
    `<div class="filters" id="havings"></div>` +
    `<div class="row sb-controls">` +
    `<button id="btn_add_filter" title="Filterbedingung (mit UND verknüpft)">Filter +</button>` +
    `<button id="btn_add_orderby" title="Sortierungsspalte hinzufügen">Sortierung +</button>` +
    `<button id="btn_add_col" title="Weitere SELECT-Spalte hinzufügen">Spalten +</button>` +
    `<button id="btn_add_having" title="Gruppen nach Aggregat filtern (HAVING)">HAVING +</button>` +
    `<label class="sb-check"><input type="checkbox" id="sb_distinct"> DISTINCT</label>` +
    `<label class="sb-limit">LIMIT <input id="sb_limit" type="number" min="1" placeholder="–"></label>` +
    `<label class="sb-dialect" title="SQL-Dialekt der generierten Abfrage">Dialekt ` +
    `<select id="sb_dialect">` +
    `<option value="sqlite">SQLite</option>` +
    `<option value="postgresql">PostgreSQL</option>` +
    `<option value="mysql">MySQL</option>` +
    `<option value="mssql">MSSQL</option>` +
    `<option value="oracle">Oracle</option></select></label>` +
    `<button id="btn_build">Generieren</button></div>` +
    `<div class="sb-fanout-hint" id="sb_fanout_hint"></div>` +
    `<ul class="path_list" id="path_list"></ul>` +
    `<div class="row sb-join-types" id="sb_join_types"></div>` +
    `<div class="sql-wrap"><button id="sql_copy" class="sql-copy" type="button" ` +
    `title="SELECT in die Zwischenablage kopieren" aria-label="SELECT kopieren">` +
    `<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" ` +
    `stroke-width="1.4"><rect x="4" y="3" width="9" height="11" rx="1.5"/>` +
    `<path d="M6 3V2.2A1.2 1.2 0 0 1 7.2 1h2.6A1.2 1.2 0 0 1 11 2.2V3"/></svg></button>` +
    `<pre class="sql_out" id="sql_out"></pre></div>` +
    `<div class="row sb-result-bar" id="sb_result_bar" style="display:none">` +
    `<label>Zeilen</label>` +
    `<select id="sb_rows">` +
    `<option value="200">200</option>` +
    `<option value="400">400</option>` +
    `<option value="0">Alle</option></select>` +
    `<button id="sb_refresh" title="Ausgabe mit aktuellen Sortierungen/Spalten neu berechnen">Aktualisieren</button>` +
    `<span id="sb_rows_info" class="hint"></span></div>` +
    `<div id="join_result"></div></div>`;
  $("start_table").addEventListener("change", () => fillCols("start_table", "start_col"));
  $("target_table").addEventListener("change", () => fillCols("target_table", "target_col"));
  wireAggColDisable($("start_agg"), $("start_col"));
  wireAggColDisable($("target_agg"), $("target_col"));
  $("btn_swap").addEventListener("click", swapStartTarget);
  $("btn_add_filter").addEventListener("click", addFilterRow);
  $("btn_add_orderby").addEventListener("click", addOrderByRow);
  $("btn_add_col").addEventListener("click", addColRow);
  $("btn_add_having").addEventListener("click", addHavingRow);
  $("btn_build").addEventListener("click", () => runBuild());
  // AP-6: refresh re-reads the form (new sort/columns) and keeps the chosen path;
  // changing the row count only re-fetches the current path (path is unaffected).
  $("sb_refresh").addEventListener("click", () => runBuild(true));
  $("sb_rows").addEventListener("change", () => renderJoinResult(SB_PATH_IDX));
  // AP-29: default the dialect to the connected backend; re-render SQL on change.
  $("sb_dialect").value = dialectFromUrl(connUrl());
  $("sb_dialect").addEventListener("change", () => runBuild(true));
  if (SCHEMA.tables.length) refillSqlBuilder();
}

// ===== SQL-Analyzer (AP-25 / AP-39) =====
// SQL-Builder path highlight and Analyzer markers are mutually exclusive views
// of the graph — clearing all of them keeps only one active at a time (AP-40:
// the blue analyzer trace must vanish once a join path is built, and vice versa).
function clearGraphHighlights() {
  if (!CY) return;
  CY.elements().removeClass(
    "hl dir-many dir-one analyze-read analyze-write analyze-edge");
}
function clearAnalyzeMarkers() { clearGraphHighlights(); }

// Colour the read/written nodes and draw the statement's JOIN edges in the graph
// (AP-39: edges, not only nodes — so the SELECT is visibly traced).
function applyAnalyzeMarkers(read, written, edges) {
  if (!CY) return;
  clearAnalyzeMarkers();
  read.forEach((t) => CY.$id(t).addClass("analyze-read"));
  written.forEach((t) => CY.$id(t).addClass("analyze-write"));
  (edges || []).forEach(([a, b]) => {
    CY.edges().forEach((e) => {
      const s = e.source().id(), t = e.target().id();
      if ((s === a && t === b) || (s === b && t === a)) e.addClass("analyze-edge");
    });
  });
}

function renderAnalyzeResult(panel, res) {
  const out = panel.querySelector("#an_result");
  if (res.parse_error) {
    // Label, then the (ANSI-stripped) error on its own line — preformatted, since
    // sqlglot includes a multi-line SQL excerpt around the offending token.
    out.innerHTML = `<p class="hint">Konnte nicht geparst werden:</p>` +
      `<pre class="an-parse-error">${esc(res.parse_error)}</pre>`;
    clearAnalyzeMarkers();
    return;
  }
  const list = (items) => (items && items.length)
    ? `<ul class="objlist">${items.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>`
    : `<p class="hint">—</p>`;
  // A section is only rendered when it has content (keeps the panel focused).
  const section = (title, items) => (items && items.length)
    ? `<h4>${esc(title)}</h4>${list(items)}` : "";
  const s = res.structure || {};
  const cx = res.complexity || {};
  const joinsTxt = (res.joins || []).map((j) =>
    `${j.kind} ${j.table}${j.on ? " · ON " + j.on : ""}`);
  const structBits = [
    `Tabellen ${s.tables ?? 0}`, `Joins ${s.joins ?? 0}`,
    `Subqueries ${s.subqueries ?? 0}`, `CTEs ${s.ctes ?? 0}`,
    `UNION ${s.unions ?? 0}`, `Window ${s.window_functions ?? 0}`,
    `Aggregate ${s.aggregates ?? 0}`, `CASE ${s.case_blocks ?? 0}`,
  ].join(" · ");
  const warns = res.warnings.length
    ? res.warnings.map((w) =>
        `<div class="an-warn an-l-${esc(w.level)}">${esc(w.message)}</div>`).join("")
    : `<p class="hint">keine Warnungen</p>`;
  out.innerHTML =
    `<div class="an-type">Typ: <strong>${esc(res.statement_type)}</strong>` +
    (cx.grade ? ` <span class="an-grade an-g-${esc(cx.grade)}" ` +
      `title="Komplexitäts-Score (gewichtet aus Joins/Subqueries/CTEs/Window/CASE)">` +
      `Komplexität ${esc(String(cx.score))} · ${esc(cx.grade)}</span>` : "") +
    (res.distinct ? ` <span class="an-pill">DISTINCT</span>` : "") + `</div>` +
    `<div class="an-struct">${esc(structBits)}</div>` +
    section("Gelesen", res.tables_read) +
    section("Geschrieben/verändert", res.tables_written) +
    section("Spalten", res.columns) +
    section("Joins", joinsTxt) +
    section("Filter (WHERE)", res.filters) +
    section("Gruppierung (GROUP BY)", res.group_by) +
    section("HAVING", res.having) +
    section("Sortierung (ORDER BY)", res.order_by) +
    (res.limit ? `<h4>LIMIT</h4><p>${esc(res.limit)}</p>` : "") +
    `<h4>Warnungen</h4>${warns}`;
  applyAnalyzeMarkers(res.tables_read, res.tables_written, res.edges);
}

async function runAnalyze(panel) {
  const sql = panel.querySelector("#an_sql").value;
  if (!sql.trim()) return;
  try {
    const res = await postJSON("/api/analyze",
      { sql, connection_url: connUrl() });
    renderAnalyzeResult(panel, res);
  } catch (e) {
    panel.querySelector("#an_result").innerHTML =
      `<p class="hint">Fehler: ${esc(e.message)}</p>`;
  }
}

function openAnalyzer() {
  const panel = ensureTab("analyzer", "SQL-Analyzer", true);
  if (panel.dataset.built) { activateTab("analyzer"); return; }
  panel.dataset.built = "1";
  panel.innerHTML =
    `<div class="analyzer">` +
    `<textarea id="an_sql" rows="14" placeholder="SQL-Statement hier einfügen … "></textarea>` +
    `<div class="row"><button id="an_run">Analysieren</button>` +
    `<span class="an-readonly" title="Der Analyzer parst nur — er führt nichts auf der Datenbank aus">read-only — wird nie ausgeführt</span></div>` +
    `<div id="an_result"></div></div>`;
  panel.querySelector("#an_run").addEventListener("click", () => runAnalyze(panel));
}

function fillCols(tableSel, colSel) {
  const t = tableByName($(tableSel).value);
  $(colSel).innerHTML = optionList(t ? t.columns.map((c) => c.name) : []);
}

function refillSqlBuilder() {
  if (!$("start_table")) return;
  const names = SCHEMA.tables.map((t) => t.name);
  $("start_table").innerHTML = optionList(names);
  $("target_table").innerHTML = optionList(names);
  fillCols("start_table", "start_col");
  fillCols("target_table", "target_col");
  $("filters").innerHTML = "";
  $("order_bys").innerHTML = "";
  $("extra_cols").innerHTML = "";
  $("path_list").innerHTML = "";
  $("sql_out").textContent = "";
  if ($("join_result")) $("join_result").innerHTML = "";
  if ($("sb_distinct")) $("sb_distinct").checked = false;
  if ($("sb_limit")) $("sb_limit").value = "";
  if ($("sb_result_bar")) $("sb_result_bar").style.display = "none";
  if ($("sb_rows_info")) $("sb_rows_info").textContent = "";
  SB_LAST = null;
  SB_PATH_IDX = 0;
}

// AP-45: distinct-value cache per (table, column) — feeds the filter-value
// dropdowns. Best-effort (empty on any error); never blocks the form.
let SB_DISTINCT_CACHE = {};
let _dlSeq = 0;   // unique id source for <datalist> elements
async function _fetchDistinct(table, column) {
  const key = table + "\u0000" + column;
  if (key in SB_DISTINCT_CACHE) return SB_DISTINCT_CACHE[key];
  try {
    const res = await postJSON("/api/distinct",
      { connection_url: connUrl(), table, column });
    SB_DISTINCT_CACHE[key] = res.values || [];
  } catch (e) { SB_DISTINCT_CACHE[key] = []; }
  return SB_DISTINCT_CACHE[key];
}

// Fill any <datalist> in a filter row with the DISTINCT values of its column,
// so the value field offers a real value dropdown while staying free-text.
async function _loadFilterDistinct(row) {
  const tEl = row.querySelector(".f-table");
  const cEl = row.querySelector(".f-col");
  const lists = row.querySelectorAll("datalist");
  if (!tEl || !cEl || !tEl.value || !cEl.value || !lists.length) return;
  const table = tEl.value, column = cEl.value;
  const values = await _fetchDistinct(table, column);
  // Race guard: if the row's column changed while this fetch was in flight, a
  // newer load now owns the datalist — don't overwrite it with stale values
  // (e.g. selecting a column fires a load for the previous default column too).
  if (tEl.value !== table || cEl.value !== column) return;
  const opts = values.map((v) => `<option value="${esc(v)}"></option>`).join("");
  lists.forEach((dl) => { dl.innerHTML = opts; });
}

// Render the value input(s) for a filter row based on the selected operator.
// AP-45: each free-text value field is backed by a <datalist> of the column's
// real DISTINCT values (loaded async, best-effort), so users can pick existing
// values without losing the ability to type anything.
function _updateFilterValueField(row) {
  const op = row.querySelector(".f-op").value;
  const wrap = row.querySelector(".f-val-wrap");
  if (op === "IS NULL" || op === "IS NOT NULL") {
    wrap.innerHTML = "";
    return;
  } else if (op === "BETWEEN") {
    const a = ++_dlSeq, b = ++_dlSeq;
    wrap.innerHTML =
      `<input class="f-val-lo" type="text" placeholder="von" list="dl${a}"><datalist id="dl${a}"></datalist>` +
      `<input class="f-val-hi" type="text" placeholder="bis" list="dl${b}"><datalist id="dl${b}"></datalist>`;
  } else if (op === "IN") {
    const a = ++_dlSeq;
    wrap.innerHTML =
      `<input class="f-val" type="text" placeholder="Wert1, Wert2, …" list="dl${a}"><datalist id="dl${a}"></datalist>`;
  } else {
    const a = ++_dlSeq;
    wrap.innerHTML = `<input class="f-val" type="text" placeholder="Wert" list="dl${a}"><datalist id="dl${a}"></datalist>`;
  }
  _loadFilterDistinct(row);
}

function addFilterRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "filter-row";
  const names = SCHEMA.tables.map((t) => t.name);
  row.innerHTML =
    `<select class="f-table">${optionList(names)}</select>` +
    `<select class="f-col"></select>` +
    `<select class="f-op">${OPERATORS.map((o) => `<option>${o}</option>`).join("")}</select>` +
    `<span class="f-val-wrap"></span>` +
    `<button type="button" class="f-del">✕</button>`;
  const fillFcol = () => {
    const t = tableByName(row.querySelector(".f-table").value);
    row.querySelector(".f-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillFcol();
  // AP-45: reload the DISTINCT dropdown whenever the column (or its table) changes.
  row.querySelector(".f-table").addEventListener("change", () => { fillFcol(); _loadFilterDistinct(row); });
  row.querySelector(".f-col").addEventListener("change", () => _loadFilterDistinct(row));
  // AP-45.1: setting a filter value (typed or picked from the DISTINCT dropdown)
  // rebuilds immediately, so the WHERE clause appears in the SQL right away. The
  // listener sits on the wrapper, so it survives the inner field being re-rendered
  // and catches `change` bubbling up from whichever value input is active.
  row.querySelector(".f-val-wrap").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".f-op").addEventListener("change", () => {
    _updateFilterValueField(row);
    // IS NULL / IS NOT NULL have no value field → they are complete on selection,
    // so apply them at once (value ops wait for the value `change` above).
    const op = row.querySelector(".f-op").value;
    if (op === "IS NULL" || op === "IS NOT NULL") _rebuildIfBuilt();
  });
  row.querySelector(".f-del").addEventListener("click", () => { row.remove(); _rebuildIfBuilt(); });
  _updateFilterValueField(row);  // render initial value field for default op "=" (loads DISTINCT)
  $("filters").appendChild(row);
}

// AP-45.1: rebuild SQL + result keeping the active path, but only once a path has
// been built (no-op on a fresh form). Used by the filter rows for live feedback.
function _rebuildIfBuilt() { if (SB_LAST) runBuild(true); }

function collectFilters() {
  const out = [];
  document.querySelectorAll("#filters .filter-row").forEach((row) => {
    const table = row.querySelector(".f-table").value;
    const column = row.querySelector(".f-col").value;
    const op = row.querySelector(".f-op").value;
    if (!table || !column || !op) return;
    if (op === "IS NULL" || op === "IS NOT NULL") {
      out.push({ table, column, op, value: null });
      return;
    }
    if (op === "BETWEEN") {
      const lo = row.querySelector(".f-val-lo");
      const hi = row.querySelector(".f-val-hi");
      if (!lo || !hi || lo.value === "" || hi.value === "") return;
      out.push({ table, column, op, value: [lo.value, hi.value] });
      return;
    }
    if (op === "IN") {
      const valEl = row.querySelector(".f-val");
      if (!valEl) return;
      const parts = valEl.value.split(",").map((s) => s.trim()).filter((s) => s !== "");
      if (!parts.length) return;
      out.push({ table, column, op, value: parts });
      return;
    }
    const valEl = row.querySelector(".f-val");
    if (!valEl || valEl.value === "") return;
    out.push({ table, column, op, value: valEl.value });
  });
  return out;
}

function addOrderByRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "orderby-row";
  const names = SCHEMA.tables.map((t) => t.name);
  row.innerHTML =
    `<select class="ob-table">${optionList(names)}</select>` +
    `<select class="ob-col"></select>` +
    `<select class="ob-agg sb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<select class="ob-dir"><option>ASC</option><option>DESC</option></select>` +
    `<button type="button" class="ob-del">✕</button>`;
  const fillOcol = () => {
    const t = tableByName(row.querySelector(".ob-table").value);
    row.querySelector(".ob-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillOcol();
  row.querySelector(".ob-table").addEventListener("change", fillOcol);
  row.querySelector(".ob-del").addEventListener("click", () => row.remove());
  wireAggColDisable(row.querySelector(".ob-agg"), row.querySelector(".ob-col"));
  $("order_bys").appendChild(row);
}

function collectOrderBy() {
  const out = [];
  document.querySelectorAll("#order_bys .orderby-row").forEach((row) => {
    const table = row.querySelector(".ob-table").value;
    const column = row.querySelector(".ob-col").value;
    const dir = row.querySelector(".ob-dir").value;
    const agg = row.querySelector(".ob-agg").value;
    if (table && column) out.push({ table, column, dir, agg });
  });
  return out;
}

function addColRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "col-row";
  const names = SCHEMA.tables.map((t) => t.name);
  row.innerHTML =
    `<select class="c-table">${optionList(names)}</select>` +
    `<select class="c-col"></select>` +
    `<select class="c-agg sb-agg" title="Aggregatfunktion">${aggOptions()}</select>` +
    `<button type="button" class="c-del">✕</button>`;
  const fillCcol = () => {
    const t = tableByName(row.querySelector(".c-table").value);
    row.querySelector(".c-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillCcol();
  row.querySelector(".c-table").addEventListener("change", fillCcol);
  row.querySelector(".c-del").addEventListener("click", () => row.remove());
  wireAggColDisable(row.querySelector(".c-agg"), row.querySelector(".c-col"));
  $("extra_cols").appendChild(row);
}

function collectExtraSelects() {
  const out = [];
  document.querySelectorAll("#extra_cols .col-row").forEach((row) => {
    const table = row.querySelector(".c-table").value;
    const column = row.querySelector(".c-col").value;
    const agg = row.querySelector(".c-agg").value;
    if (table && column) out.push({ table, column, agg });
  });
  return out;
}

function addHavingRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "having-row";
  const names = SCHEMA.tables.map((t) => t.name);
  row.innerHTML =
    `<select class="h-agg sb-agg" title="Aggregatfunktion">` +
    aggOptionTags() + `</select>` +
    `<select class="h-table">${optionList(names)}</select>` +
    `<select class="h-col"></select>` +
    `<select class="h-op">${HAVING_OPS.map((o) => `<option>${o}</option>`).join("")}</select>` +
    `<input class="h-val" type="text" placeholder="Wert">` +
    `<button type="button" class="h-del">✕</button>`;
  const fillHcol = () => {
    const t = tableByName(row.querySelector(".h-table").value);
    row.querySelector(".h-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillHcol();
  row.querySelector(".h-table").addEventListener("change", fillHcol);
  row.querySelector(".h-val").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-agg").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-op").addEventListener("change", _rebuildIfBuilt);
  row.querySelector(".h-del").addEventListener("click", () => { row.remove(); _rebuildIfBuilt(); });
  wireAggColDisable(row.querySelector(".h-agg"), row.querySelector(".h-col"));
  $("havings").appendChild(row);
}

function collectHaving() {
  const out = [];
  document.querySelectorAll("#havings .having-row").forEach((row) => {
    const table = row.querySelector(".h-table").value;
    const column = row.querySelector(".h-col").value;
    const agg = row.querySelector(".h-agg").value;
    const op = row.querySelector(".h-op").value;
    const value = row.querySelector(".h-val").value;
    if (table && column && agg && op && value !== "") {
      out.push({ table, column, agg, op, value });
    }
  });
  return out;
}

// Read the full SQL-Builder form into a /api/joinpath request body.
// Swap Start ⇄ Ziel (table + column). Handy because the warning-free direction
// is often just the reverse: ascending toward a parent never fans out. Repopulates
// each column dropdown for its new table before restoring the column value, mirrors
// the graph source/target markers, and rebuilds if a path was already shown.
function swapStartTarget() {
  const stv = $("start_table").value, scv = $("start_col").value;
  const ttv = $("target_table").value, tcv = $("target_col").value;
  $("start_table").value = ttv; fillCols("start_table", "start_col"); $("start_col").value = tcv;
  $("target_table").value = stv; fillCols("target_table", "target_col"); $("target_col").value = scv;
  if ($("start_agg") && $("target_agg")) {
    const sa = $("start_agg").value;
    $("start_agg").value = $("target_agg").value;
    $("target_agg").value = sa;
  }
  // Keep the graph markers consistent with the selection
  const s = GRAPH_SEL.source;
  GRAPH_SEL.source = GRAPH_SEL.target;
  GRAPH_SEL.target = s;
  _updateUmlMarks();
  _updateGraphNodeMarkers();
  if (SB_LAST) runBuild();
}

function collectJoinBody() {
  const limitRaw = $("sb_limit") ? $("sb_limit").value.trim() : "";
  return {
    connection_url: connUrl(),
    start: { table: $("start_table").value, column: $("start_col").value,
             agg: $("start_agg") ? $("start_agg").value : "" },
    target: { table: $("target_table").value, column: $("target_col").value,
              agg: $("target_agg") ? $("target_agg").value : "" },
    filters: collectFilters(),
    extra_selects: collectExtraSelects(),
    include_implied: includeImplied(),
    distinct: $("sb_distinct") ? $("sb_distinct").checked : false,
    order_by: collectOrderBy(),
    having: collectHaving(),
    limit: limitRaw !== "" ? parseInt(limitRaw, 10) : null,
    dialect: $("sb_dialect") ? $("sb_dialect").value : "sqlite",
    join_types: SB_JOIN_TYPES,   // AP-41: per-step join types (INNER default)
  };
}

// AP-29: derive the default SQL dialect from the active connection URL
// (e.g. "postgresql+psycopg2://…" → postgresql). SQLite is the fallback.
function dialectFromUrl(url) {
  const scheme = (url || "").split("://")[0].split("+")[0].toLowerCase();
  return ["sqlite", "postgresql", "mysql", "mssql", "oracle"].includes(scheme)
    ? scheme : "sqlite";
}

// Selected output row count: 200/400, or null ("Alle" → server's hard cap).
function sbSelectedMaxRows() {
  const sel = $("sb_rows");
  if (!sel) return 200;
  return sel.value === "0" ? null : parseInt(sel.value, 10);
}

// AP-41: render one join-type dropdown per step of the active path. Changing a
// type updates SB_JOIN_TYPES (per step) and rebuilds the SQL (and result).
const SB_JOIN_OPTS = ["INNER", "LEFT", "RIGHT", "FULL"];
function renderJoinTypeControls(i) {
  const box = $("sb_join_types");
  if (!box) return;
  const steps = (SB_LAST && SB_LAST.paths[i] && SB_LAST.paths[i].steps) || [];
  if (!steps.length) { box.innerHTML = ""; return; }
  box.innerHTML = `<span class="jt-lbl">Join-Typ:</span>` + steps.map((s, k) => {
    const cur = (SB_JOIN_TYPES[k] || "INNER").toUpperCase();
    const opts = SB_JOIN_OPTS.map((o) =>
      `<option${o === cur ? " selected" : ""}>${o}</option>`).join("");
    return `<label class="jt-step" title="${escAttr(s.left)} → ${escAttr(s.right)}">` +
      `${esc(s.left)}→${esc(s.right)} <select data-step="${k}">${opts}</select>` +
      `<span class="jt-orphan" data-step="${k}"></span></label>`;
  }).join("");
  box.querySelectorAll("select").forEach((sel) =>
    sel.addEventListener("change", () => {
      SB_JOIN_TYPES[+sel.dataset.step] = sel.value;
      runBuild(true);   // regenerate SQL + result with the new join types
    }));
  _loadOrphans(i).then(() => _applyOrphanHints(i));   // AP-47: flag orphan-revealing types
}

// AP-47: which join types at each step would actually change the result (count-
// based, path-context aware). Result depends on the other steps' current types,
// so the cache key includes the join-type signature. Best-effort, never blocks.
let SB_ORPHANS_CACHE = {};
function _orphanKey(i) { return i + ":" + SB_JOIN_TYPES.join(","); }
async function _loadOrphans(i) {
  const key = _orphanKey(i);
  if (SB_ORPHANS_CACHE[key] || !SB_LAST) return;
  try {
    const res = await postJSON("/api/orphan_check",
      Object.assign({}, SB_LAST.body, { path_index: i }));
    SB_ORPHANS_CACHE[key] = res.steps || [];
  } catch (e) { SB_ORPHANS_CACHE[key] = []; }
}

function _applyOrphanHints(i) {
  const flags = SB_ORPHANS_CACHE[_orphanKey(i)];
  const box = $("sb_join_types");
  if (!flags || !box) return;
  box.querySelectorAll("select").forEach((sel) => {
    const f = flags[+sel.dataset.step];
    if (!f) return;
    // Tint the join types that would change the result (best effort — native
    // <option> background support varies by browser/OS).
    [...sel.options].forEach((opt) => {
      const t = opt.value.toLowerCase();
      const eff = !!f[t];
      opt.style.background = eff ? "#fbeccf" : "";
      opt.classList.toggle("opt-orphan", eff);
    });
  });
  // Reliable, always-visible marker chip next to each dropdown.
  box.querySelectorAll(".jt-orphan").forEach((span) => {
    const f = flags[+span.dataset.step] || {};
    const marks = ["left", "right", "full"]
      .filter((t) => f[t]).map((t) => t.toUpperCase());
    span.innerHTML = marks.length
      ? `<span class="jt-orphan-chip" title="Diese Join-Typen ändern hier das Ergebnis (zusätzliche unverknüpfte Zeilen)">⚠ ${marks.join("/")}</span>`
      : "";
  });
}

// Mark the active path with [*] and the rest with [ ] (AP-47), so the chosen
// alternative is obvious — replacing the plain bullet list.
function _markActivePath() {
  const list = $("path_list");
  if (!list) return;
  list.querySelectorAll("li").forEach((li) => {
    const active = +li.dataset.i === SB_PATH_IDX;
    li.classList.toggle("active", active);
    const m = li.querySelector(".path-mark");
    if (m) m.textContent = active ? "[*]" : "[ ]";
  });
}

// ===== AP-45: result column-header actions (sort / filter / remove) =====

// A start/target column defines the join path and cannot be dropped from output.
function _isAnchorColumn(table, column) {
  return ($("start_table").value === table && $("start_col").value === column) ||
         ($("target_table").value === table && $("target_col").value === column);
}

// Add an ORDER BY for (table, column, dir), replacing any existing sort on the
// same column, then rebuild keeping the active path so the result re-sorts.
function _sortByColumn(table, column, dir) {
  document.querySelectorAll("#order_bys .orderby-row").forEach((row) => {
    if (row.querySelector(".ob-table").value === table &&
        row.querySelector(".ob-col").value === column) row.remove();
  });
  addOrderByRow();
  const row = $("order_bys").lastElementChild;
  const tEl = row.querySelector(".ob-table");
  tEl.value = table;
  tEl.dispatchEvent(new Event("change"));   // repopulate the column dropdown
  row.querySelector(".ob-col").value = column;
  row.querySelector(".ob-dir").value = dir;
  if (SB_LAST) runBuild(true);
}

// Add a filter row pre-set to (table, column) with op "=", focus its value field
// (which loads the DISTINCT dropdown). The build only changes once a value is set.
function _filterByColumn(table, column) {
  addFilterRow();
  const row = $("filters").lastElementChild;
  const tEl = row.querySelector(".f-table");
  tEl.value = table;
  tEl.dispatchEvent(new Event("change"));   // repopulate the column dropdown + DISTINCT
  row.querySelector(".f-col").value = column;
  _loadFilterDistinct(row);
  const valEl = row.querySelector(".f-val");
  if (valEl) valEl.focus();
  row.scrollIntoView({ block: "nearest" });
}

// Remove an extra-select column from the output and rebuild. Start/target anchor
// columns define the path and are refused (the menu item is disabled too).
function _removeColumn(table, column) {
  if (_isAnchorColumn(table, column)) return;
  let removed = false;
  document.querySelectorAll("#extra_cols .col-row").forEach((row) => {
    if (row.querySelector(".c-table").value === table &&
        row.querySelector(".c-col").value === column) { row.remove(); removed = true; }
  });
  if (removed && SB_LAST) runBuild(true);
}

let _colMenuEl = null;
function _closeColMenu() {
  if (_colMenuEl) { _colMenuEl.remove(); _colMenuEl = null; }
  document.removeEventListener("click", _closeColMenu, true);
}

// Open the actions popup under a result header cell.
function _showColMenu(th, meta) {
  _closeColMenu();
  const anchor = _isAnchorColumn(meta.table, meta.column);
  const m = document.createElement("div");
  m.className = "col-menu";
  m.innerHTML =
    `<button data-act="asc">▲ Sortieren ASC</button>` +
    `<button data-act="desc">▼ Sortieren DESC</button>` +
    `<button data-act="filter">≡ Als Filter…</button>` +
    `<button data-act="remove"${anchor ? " disabled title='Start-/Ziel-Spalte definiert den Pfad'" : ""}>✕ Spalte entfernen</button>`;
  document.body.appendChild(m);
  const r = th.getBoundingClientRect();
  m.style.left = (window.scrollX + r.left) + "px";
  m.style.top = (window.scrollY + r.bottom) + "px";
  m.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (b.disabled) return;
      const act = b.dataset.act;
      if (act === "asc") _sortByColumn(meta.table, meta.column, "ASC");
      else if (act === "desc") _sortByColumn(meta.table, meta.column, "DESC");
      else if (act === "filter") _filterByColumn(meta.table, meta.column);
      else if (act === "remove") _removeColumn(meta.table, meta.column);
      _closeColMenu();
    }));
  _colMenuEl = m;
  // Defer the outside-click closer so the opening click doesn't immediately fire it.
  setTimeout(() => document.addEventListener("click", _closeColMenu, true), 0);
}

// Execute the SELECT for path `i` and render its rows into #join_result.
async function renderJoinResult(i) {
  if (!SB_LAST || !SB_LAST.paths[i]) return;
  SB_PATH_IDX = i;
  _markActivePath();
  // Show the runnable, value-inlined SQL (copy uses this text too); the server
  // still executes the parameterised form server-side from the form body.
  $("sql_out").textContent = SB_LAST.paths[i].sql_inline || SB_LAST.paths[i].sql;
  renderJoinTypeControls(i);
  highlightPath(SB_LAST.paths[i].steps || SB_LAST.paths[i].edges || []);
  const resultEl = $("join_result");
  if (!resultEl) return;
  resultEl.innerHTML = "<p class='hint'>lädt…</p>";
  const info = $("sb_rows_info");
  if (info) info.textContent = "";
  try {
    const runBody = Object.assign({}, SB_LAST.body,
      { path_index: i, max_rows: sbSelectedMaxRows() });
    const res = await postJSON("/api/joinpath/run", runBody);
    if (!res.rows.length) {
      resultEl.innerHTML = "<p class='hint'>keine Ergebniszeilen</p>";
      return;
    }
    // AP-45: each header carries its source (table, column) so a click opens an
    // actions menu (sort / filter / remove). columns_meta is in selection order.
    const meta = res.columns_meta || [];
    const thead = res.columns.map((c, idx) => {
      const cm = meta[idx];
      const attrs = cm ? ` data-table="${esc(cm.table)}" data-col="${esc(cm.column)}"` : "";
      const cls = cm ? "th-actionable" : "";
      return `<th class="${cls}"${attrs}>${esc(c)}${cm ? `<span class="th-caret">▾</span>` : ""}</th>`;
    }).join("");
    const tbody = res.rows.map((r) =>
      "<tr>" + r.map((v) => v === null
        ? `<td class="null-cell"><i>NULL</i></td>`   // AP-44: orphan/outer-join cells stand out
        : `<td>${esc(v)}</td>`).join("") + "</tr>"
    ).join("");
    resultEl.innerHTML =
      `<table class="cols"><thead><tr>${thead}</tr></thead>` +
      `<tbody>${tbody}</tbody></table>`;
    resultEl.querySelectorAll("th.th-actionable").forEach((th) =>
      th.addEventListener("click", (ev) => {
        ev.stopPropagation();
        _showColMenu(th, { table: th.dataset.table, column: th.dataset.col });
      }));
    if (info) {
      // AP-44: richer status line — rows · join-type · fan-out flag.
      const cap = res.row_cap || res.rows.length;
      const steps = SB_LAST.paths[i].steps || [];
      const types = steps.map((s, k) => (SB_JOIN_TYPES[k] || "INNER").toUpperCase());
      const uniq = [...new Set(types)];
      const typeLabel = uniq.length === 0 ? "" : uniq.length === 1 ? uniq[0] : "gemischt";
      const fanout = steps.some((s) => s.to_many);
      const parts = [
        res.rows.length >= cap
          ? `${res.rows.length} Zeilen (begrenzt auf ${cap})`
          : `${res.rows.length} Zeilen`,
      ];
      if (typeLabel) parts.push(typeLabel);
      info.innerHTML = esc(parts.join(" · ")) +
        (fanout ? ` · <span class="info-fanout">⚠ 1-N</span>` : "");
    }
  } catch (e) {
    resultEl.innerHTML = `<p class='hint'>Fehler: ${esc(e.message)}</p>`;
  }
}

// Render a join path as a table sequence with a direction chip on every join:
// green "N-1" (ascending, safe) or amber "1-N" (descending, can fan out). Makes
// it obvious that a path is a *mix*, not "all descending". Falls back to a plain
// arrow sequence if the API didn't send per-step directions.
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

// Build join paths from the current form. `preserveIndex` keeps the selected
// path (used by "Aktualisieren" after a sort/column change); a fresh build
// from "Generieren" resets to the first path.
async function runBuild(preserveIndex = false) {
  // A fresh build (not a refresh) resets per-step join types to INNER (AP-41)
  // and the cached orphan-flags (AP-47).
  if (!preserveIndex) { SB_JOIN_TYPES = []; SB_ORPHANS_CACHE = {}; }
  const body = collectJoinBody();
  try {
    const data = await postJSON("/api/joinpath", body);
    SB_LAST = { body, paths: data.paths };
    // Mirror the form's start/target into the graph markers so the built path
    // shows green Start / red Ziel rings — matching the legend even when the
    // selection was made via the dropdowns rather than by clicking nodes.
    if (body.start && body.start.table && body.target && body.target.table) {
      GRAPH_SEL.source = { table: body.start.table, column: body.start.column };
      GRAPH_SEL.target = { table: body.target.table, column: body.target.column };
      _updateGraphNodeMarkers();
      // AP-46: a fresh build opens the field cards for start + target (the same
      // cards a node double-click shows), so they appear even when the selection
      // was made via the dropdowns rather than by clicking the graph.
      if (!preserveIndex) {
        if ($("uml_cards")) $("uml_cards").innerHTML = "";
        showUmlCard(body.target.table);   // added last -> ends up on top
        showUmlCard(body.start.table);
        _updateUmlMarks();                // mark the chosen start/target columns
      }
    }
    const prev = SB_PATH_IDX;
    SB_PATH_IDX = preserveIndex && prev < data.paths.length ? prev : 0;
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
    const bar = $("sb_result_bar");
    if (data.paths.length) {
      if (bar) bar.style.display = "";
      renderJoinResult(SB_PATH_IDX);
    } else {
      if (bar) bar.style.display = "none";
      $("sql_out").textContent = "";
      $("join_result").innerHTML = "";
      if ($("sb_join_types")) $("sb_join_types").innerHTML = "";
      if ($("sb_fanout_hint")) $("sb_fanout_hint").innerHTML = "";
    }
  } catch (e) { alert(e.message); }
}

// ===== UML card area (AP-1) =====
// AP-46: the detail area below the graph is hidden while nothing is selected
// (graph stays centered) and appears — pushing the graph up — once a table is
// selected (via a node double-click OR via the SQL-Builder start/target).
function _updateUmlAreaVisibility() {
  const area = $("uml_area");
  if (!area) return;
  const hasCards = $("uml_cards") && $("uml_cards").children.length > 0;
  const hasSel = !!(GRAPH_SEL.source || GRAPH_SEL.target);
  const next = (hasCards || hasSel) ? "block" : "none";
  if (area.style.display !== next) {
    area.style.display = next;
    // Graph height changed: recompute the canvas and re-center at the SAME zoom
    // so the graph slides up/down and stays centered in its area (no zoom jump).
    if (CY) requestAnimationFrame(() => {
      CY.resize();
      CY.center();
    });
  }
}

function showUmlCard(tableName) {
  const t = tableByName(tableName);
  if (!t) return;
  const cards = $("uml_cards");
  if (!cards) return;

  // If card already exists, move it to the front
  let card = cards.querySelector(`.uml-card[data-table="${CSS.escape(tableName)}"]`);
  if (card) { cards.insertBefore(card, cards.firstChild); _updateUmlAreaVisibility(); return; }

  card = document.createElement("div");
  card.className = "uml-card";
  card.dataset.table = tableName;

  const colsHtml = t.columns.map((c) => {
    const pk = c.pk ? ` <span class="badge">PK</span>` : "";
    const tip = c.comment ? ` title="${escAttr(c.comment)}"` : "";
    return `<div class="uml-col"${tip} data-table="${esc(tableName)}" data-col="${esc(c.name)}">${esc(c.name)}${pk}<span class="uml-col-type">${esc(c.type)}</span></div>`;
  }).join("");

  const headTip = t.comment ? ` title="${escAttr(t.comment)}"` : "";
  card.innerHTML = `<div class="uml-card-head"${headTip}>${esc(tableName)}</div>${colsHtml}`;
  card.querySelectorAll(".uml-col").forEach((row) => {
    row.addEventListener("click", () => selectColumn(row.dataset.table, row.dataset.col));
  });
  cards.insertBefore(card, cards.firstChild);
  _updateUmlAreaVisibility();
}

function _updateUmlMarks() {
  document.querySelectorAll(".uml-col.sel-source, .uml-col.sel-target").forEach((el) => {
    el.classList.remove("sel-source", "sel-target");
  });
  if (GRAPH_SEL.source) {
    const el = document.querySelector(
      `.uml-col[data-table="${CSS.escape(GRAPH_SEL.source.table)}"][data-col="${CSS.escape(GRAPH_SEL.source.column)}"]`
    );
    if (el) el.classList.add("sel-source");
  }
  if (GRAPH_SEL.target) {
    const el = document.querySelector(
      `.uml-col[data-table="${CSS.escape(GRAPH_SEL.target.table)}"][data-col="${CSS.escape(GRAPH_SEL.target.column)}"]`
    );
    if (el) el.classList.add("sel-target");
  }
}

function _updateGraphNodeMarkers() {
  if (!CY) return;
  CY.nodes().removeClass("sel-source sel-target");
  if (GRAPH_SEL.source) CY.$id(GRAPH_SEL.source.table).addClass("sel-source");
  if (GRAPH_SEL.target) CY.$id(GRAPH_SEL.target.table).addClass("sel-target");
  _updateUmlAreaVisibility();
}

function _updateStatusBar() {
  const bar = $("uml_status");
  if (!bar) return;
  if (!GRAPH_SEL.source) { bar.textContent = ""; return; }
  let txt = `Quelle: ${GRAPH_SEL.source.table}.${GRAPH_SEL.source.column}`;
  if (GRAPH_SEL.target) txt += ` → Ziel: ${GRAPH_SEL.target.table}.${GRAPH_SEL.target.column}`;
  bar.textContent = txt;
}

function selectColumn(tableName, colName) {
  if (!GRAPH_SEL.source) {
    GRAPH_SEL.source = { table: tableName, column: colName };
  } else if (!GRAPH_SEL.target) {
    if (GRAPH_SEL.source.table === tableName) {
      $("uml_status").textContent =
        `Quelle: ${GRAPH_SEL.source.table}.${GRAPH_SEL.source.column} — Ziel muss eine andere Tabelle sein`;
      return;
    }
    GRAPH_SEL.target = { table: tableName, column: colName };
    _updateStatusBar();
    _updateUmlMarks();
    _updateGraphNodeMarkers();
    applyGraphSelection();
    return;
  } else {
    // Both already set: start a new selection
    resetGraphSelection();
    GRAPH_SEL.source = { table: tableName, column: colName };
  }
  _updateStatusBar();
  _updateUmlMarks();
  _updateGraphNodeMarkers();
}

async function applyGraphSelection() {
  if (!GRAPH_SEL.source || !GRAPH_SEL.target) return;
  const src = GRAPH_SEL.source;
  const tgt = GRAPH_SEL.target;
  openSqlBuilder();
  $("start_table").value = src.table;
  fillCols("start_table", "start_col");
  $("start_col").value = src.column;
  $("target_table").value = tgt.table;
  fillCols("target_table", "target_col");
  $("target_col").value = tgt.column;
  activateTab("sqlbuilder");
  await runBuild();
}

function resetGraphSelection() {
  GRAPH_SEL = { source: null, target: null };
  _updateStatusBar();
  _updateUmlMarks();
  _updateGraphNodeMarkers();
}

// AP-8: the "Auswahl zurücksetzen" button must fully clean up — not just the
// source/target markers, but also the highlighted join path in the graph and
// the UML cards opened below it. (The internal reset above keeps the cards so
// the user can click on a card to start a fresh selection.)
function clearSelectionAndCards() {
  resetGraphSelection();
  clearGraphHighlights();   // join path + analyzer markers
  if ($("uml_cards")) $("uml_cards").innerHTML = "";  // close the cards below
  _updateUmlAreaVisibility();   // nothing selected -> hide area, graph re-centers
}

// ===== Schema graph =====
async function drawGraph() {
  const g = await postJSON("/api/graph", {
    connection_url: connUrl(), include_implied: includeImplied(),
  });
  if (CY) CY.destroy();

  // Reset UML selection state and clear cards on every graph (re)build
  GRAPH_SEL = { source: null, target: null };
  if ($("uml_cards")) $("uml_cards").innerHTML = "";
  if ($("uml_status")) $("uml_status").textContent = "";
  _updateUmlAreaVisibility();   // freshly drawn graph starts centered (area hidden)

  const elements = [
    ...g.nodes.map((n) => ({ data: { id: n.id } })),
    ...g.edges.map((e) => ({
      data: { source: e.source, target: e.target, implied: !!e.implied },
    })),
  ];
  CY = cytoscape({
    container: $("graph"),
    elements,
    // AP-7: finer mouse-wheel zoom (default 1 jumps too far) + zoom bounds
    // that match the slider range (10 %–400 %).
    wheelSensitivity: 0.2,
    minZoom: 0.1,
    maxZoom: 4,
    style: [
      { selector: "node", style: {
        label: "data(id)", "font-size": 9, color: "#fff",
        "background-color": "#2E6FAE", "text-valign": "center",
        "text-halign": "center", shape: "round-rectangle",
        width: 84, height: 24, "text-wrap": "wrap", "text-max-width": 78 } },
      { selector: "edge", style: {
        "line-color": "#bbb", width: 2, "curve-style": "bezier" } },
      { selector: "edge[?implied]", style: {
        "line-style": "dashed", "line-color": "#9b59b6" } },
      { selector: "node.hl", style: {
        "background-color": "#E0532E", "border-width": 2, "border-color": "#7a1f0a" } },
      // Highlighted join path: orange edges, each carrying a direction label
      // (N-1 / 1-N) so the whole path reads as a mix, not "all descending".
      { selector: "edge.hl", style: {
        "line-color": "#E0532E", width: 4,
        label: "data(dir)", "font-size": 9, "font-weight": "bold",
        "text-rotation": "autorotate",
        "text-background-color": "#fff", "text-background-opacity": 0.9,
        "text-background-padding": 2,
        "text-border-width": 1, "text-border-opacity": 1, "text-border-color": "#ccc" } },
      { selector: "edge.hl.dir-many", style: { color: "#9a6700" } },  // amber = 1-N (fan-out)
      { selector: "edge.hl.dir-one",  style: { color: "#1e7e34" } },  // green = N-1 (safe)
      // Endpoints get a full fill so they stand out against the orange path:
      // green start, amber/gold target (red blended with the orange). Amber needs
      // dark label text to stay readable (nodes default to white text).
      { selector: "node.sel-source", style: {
        "background-color": "#1e7e34", "border-width": 3, "border-color": "#13532299" } },
      { selector: "node.sel-target", style: {
        "background-color": "#f3b305", color: "#222",
        "border-width": 3, "border-color": "#9a7300" } },
      { selector: "node.analyze-read",  style: { "background-color": "#1a73e8" } },
      { selector: "node.analyze-write", style: { "background-color": "#d93025" } },
      { selector: "edge.analyze-edge", style: {
        "line-color": "#1a73e8", width: 4, "target-arrow-color": "#1a73e8" } },
    ],
  });
  // Register dbltap handler: opens the UML card for the clicked table node
  CY.on("dbltap", "node", (e) => showUmlCard(e.target.id()));
  // AP-7: keep the zoom slider + % label in sync with wheel/pinch zoom
  CY.on("zoom", updateZoomUI);

  window.CY = CY;  // expose for browser-console debugging and e2e checks
  runGraphLayout();
}

// AP-16: hierarchical (dagre) layout — the FK graph is directional, so a layered
// Sugiyama layout minimizes edge crossings far better than force-directed cose.
// rankDir BT puts referenced (parent) tables above their children. Deterministic,
// so "Neu anordnen" resets to this clean layout after manual node dragging.
//
// We drive dagre directly via the bundled window.dagre. Edges are drawn as straight
// lines (cytoscape's default): a deliberate trade-off — routing rank-skipping edges
// through dagre's bend points removes the last 1 crossing but makes the connections
// look noticeably worse (zig-zags). Clean straight lines + at most a crossing or two
// read better, so we only position nodes here and leave edges straight.
function runGraphLayout() {
  if (!CY || !window.dagre) return;
  const dagre = window.dagre;
  const dense = CY.nodes().length > 12;
  const g = new dagre.graphlib.Graph({ multigraph: true })
    .setGraph({
      rankdir: "BT",                 // referenced tables on top
      ranker: "network-simplex",     // tighter, crossing-minimized ranks
      nodesep: dense ? 24 : 18,      // separation within a rank
      ranksep: dense ? 120 : 90,     // separation between ranks (fills panel height)
      edgesep: 10,
    })
    .setDefaultEdgeLabel(() => ({}));

  CY.nodes().forEach((n) => {
    const bb = n.layoutDimensions({});
    g.setNode(n.id(), { width: bb.w, height: bb.h });
  });
  CY.edges().forEach((e) =>
    g.setEdge(e.source().id(), e.target().id(), {}, e.id()));

  dagre.layout(g);

  CY.batch(() => {
    CY.nodes().forEach((n) => {
      const dn = g.node(n.id());
      if (dn) n.position({ x: dn.x, y: dn.y });
    });
  });
  CY.fit(undefined, GRAPH_FIT_PAD);
  updateZoomUI();
}

// ===== Graph zoom control (AP-7) =====
function updateZoomUI() {
  if (!CY) return;
  const pct = Math.round(CY.zoom() * 100);
  const slider = $("zoom_slider");
  const label = $("zoom_pct");
  if (slider) slider.value = Math.max(10, Math.min(400, pct));
  if (label) label.textContent = pct + "%";
}

function setupZoomControl() {
  const slider = $("zoom_slider");
  if (!slider) return;
  slider.addEventListener("input", () => {
    if (!CY) return;
    const level = parseInt(slider.value, 10) / 100;
    const c = CY.container();
    // Zoom around the viewport centre so the slider feels predictable.
    CY.zoom({ level, renderedPosition: { x: c.clientWidth / 2, y: c.clientHeight / 2 } });
    const label = $("zoom_pct");
    if (label) label.textContent = Math.round(CY.zoom() * 100) + "%";
  });
}

// Highlight the active join path in the graph. Accepts step objects
// ({left, right, to_many}) so each edge gets a direction label (N-1 / 1-N) and
// colour; falls back to legacy [a, b] pairs (then unlabelled).
function highlightPath(steps) {
  if (!CY) return;
  clearGraphHighlights();   // also drops any stale analyzer markers (AP-40)
  const nodes = new Set();
  for (const st of steps) {
    const a = st.left ?? st[0];
    const b = st.right ?? st[1];
    const toMany = !!st.to_many;
    nodes.add(a);
    nodes.add(b);
    CY.edges().forEach((e) => {
      const s = e.source().id(), t = e.target().id();
      if ((s === a && t === b) || (s === b && t === a)) {
        e.addClass("hl").addClass(toMany ? "dir-many" : "dir-one");
        if (st.left !== undefined) e.data("dir", toMany ? "1-N" : "N-1");
      }
    });
  }
  nodes.forEach((id) => CY.$id(id).addClass("hl"));
}

// ===== Resizable splitter (graph panel width) =====
function setupSplitter() {
  const splitter = $("splitter");
  let dragging = false;
  splitter.addEventListener("mousedown", (e) => {
    dragging = true; splitter.classList.add("dragging");
    document.body.style.userSelect = "none"; e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const w = window.innerWidth - e.clientX;
    const clamped = Math.max(220, Math.min(w, window.innerWidth - 420));
    document.documentElement.style.setProperty("--graph-width", clamped + "px");
    if (CY) CY.resize();
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false; splitter.classList.remove("dragging");
    document.body.style.userSelect = "";
    if (CY) { CY.resize(); CY.fit(undefined, GRAPH_FIT_PAD); }
  });
}

// AP-13: left splitter resizes the sidebar (object-browser) width.
function setupLeftSplitter() {
  const splitter = $("splitter_left");
  if (!splitter) return;
  let dragging = false;
  splitter.addEventListener("mousedown", (e) => {
    dragging = true; splitter.classList.add("dragging");
    document.body.style.userSelect = "none"; e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const clamped = Math.max(160, Math.min(e.clientX, 520));
    document.documentElement.style.setProperty("--sidebar-width", clamped + "px");
    if (CY) CY.resize();
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false; splitter.classList.remove("dragging");
    document.body.style.userSelect = "";
    if (CY) { CY.resize(); CY.fit(undefined, GRAPH_FIT_PAD); }
  });
}

// ===== Schema picker — populate dropdown after connecting =====
async function populateSchemas() {
  const sel = $("schema_select");
  if (!sel) return;
  let list = [];
  try {
    const res = await postJSON("/api/schemas", { connection_url: connUrl() });
    list = (res && res.schemas) || [];
  } catch (_e) { list = []; }
  sel.style.display = "";  // schema picker stays visible (with a label)
  if (list.length === 1) {
    // only one schema possible → preselect it by default
    SELECTED_SCHEMA = list[0];
    sel.innerHTML = list.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
    sel.value = SELECTED_SCHEMA;
  } else {
    sel.innerHTML = '<option value="">— Standard-Schema —</option>'
      + list.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join("");
    sel.value = SELECTED_SCHEMA;
  }
}

// ===== Connect with the current URL (hidden field) =====
async function doConnect() {
  try {
    await populateSchemas();
    SCHEMA = await postJSON("/api/schema", { connection_url: connUrl() });
    document.querySelectorAll(".tab").forEach((t) => closeTab(t.dataset.tab));
    renderSidebar();
    openSqlBuilder();
    refillSqlBuilder();
    activateTab("sqlbuilder");
    await drawGraph();
    $("status").textContent =
      `verbunden — ${SCHEMA.tables.length} Tabellen, ${SCHEMA.views.length} Views`;
  } catch (e) {
    $("status").textContent = "";
    alert(e.message);
  }
}

// ===== Connection manager tab =====
function connFieldsHtml(dbType, c) {
  c = c || {};
  if (dbType === "sqlite") {
    return `<div class="row"><label>Dateipfad</label>` +
      `<input id="cf_filepath" type="text" placeholder="/pfad/zur.db" ` +
      `value="${esc(c.filepath || "")}" style="flex:1"></div>`;
  }
  const port = c.port || PORT_DEFAULTS[dbType] || "";
  let html =
    `<div class="row"><label>Host</label><input id="cf_host" type="text" ` +
    `placeholder="localhost" value="${esc(c.host || "")}"></div>` +
    `<div class="row"><label>Port</label><input id="cf_port" type="number" ` +
    `value="${esc(port)}"></div>`;
  // Oracle uses service_name instead of database
  if (dbType === "oracle") {
    html += `<div class="row"><label>Service-Name</label><input id="cf_service_name" ` +
      `type="text" placeholder="XEPDB1" value="${esc(c.service_name || "")}"></div>`;
  } else {
    html += `<div class="row"><label>Datenbank</label><input id="cf_database" type="text" ` +
      `value="${esc(c.database || "")}"></div>`;
  }
  html +=
    `<div class="row"><label>Benutzer</label><input id="cf_user" type="text" ` +
    `value="${esc(c.user || "")}"></div>` +
    `<div class="row"><label>Passwort</label><input id="cf_password" type="password"></div>`;
  // AP-12: MSSQL-Verschlüsselungsoptionen. Tri-State — "Standard" lässt den
  // Parameter weg (build_url nimmt nichts Unsicheres an).
  if (dbType === "mssql") {
    const tri = (id, label, val) => {
      const opt = (v, t) =>
        `<option value="${v}"${(val || "") === v ? " selected" : ""}>${t}</option>`;
      return `<div class="row"><label>${label}</label><select id="${id}">` +
        opt("", "Standard") + opt("yes", "ja") + opt("no", "nein") + `</select></div>`;
    };
    html += tri("cf_encrypt", "Verschlüsselung", c.encrypt) +
            tri("cf_trust", "Server-Zertifikat vertrauen", c.trust_server_certificate);
  }
  return html;
}

function renderConnFields(c) {
  $("conn_fields").innerHTML = connFieldsHtml($("conn_type").value, c);
}

function formParams() {
  const t = $("conn_type").value;
  if (t === "sqlite") return { db_type: t, filepath: $("cf_filepath").value };
  const p = {
    db_type: t, host: $("cf_host").value, port: $("cf_port").value,
    user: $("cf_user").value, password: $("cf_password").value,
  };
  // Oracle uses service_name; all other network types use database
  if (t === "oracle") p.service_name = $("cf_service_name").value;
  else p.database = $("cf_database").value;
  if (t === "mssql") {
    p.encrypt = $("cf_encrypt") ? $("cf_encrypt").value : "";
    p.trust_server_certificate = $("cf_trust") ? $("cf_trust").value : "";
  }
  return p;
}

// AP-10: keep both connection pickers (topbar dropdown + connection tab) fed
// from the same saved-connections list, preserving each one's current value.
async function refreshSavedConnections() {
  try {
    const r = await fetch("/api/connections");
    SAVED_CONNS = (await r.json()).connections || [];
  } catch (e) { SAVED_CONNS = []; }
  const options = (placeholder) =>
    `<option value="">${placeholder}</option>` +
    SAVED_CONNS.map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join("");
  const tb = $("topbar_conn");
  if (tb) { const keep = tb.value; tb.innerHTML = options("— gespeicherte Verbindung —"); tb.value = keep; }
  const cs = $("conn_saved");
  if (cs) { const keep = cs.value; cs.innerHTML = options("— neu —"); cs.value = keep; }
}

// Mirror the active saved-connection name into both pickers (two-way sync).
function syncConnSelectors(name) {
  const tb = $("topbar_conn"); if (tb) tb.value = name || "";
  const cs = $("conn_saved"); if (cs) cs.value = name || "";
}

// Prefill the connection-tab form from a saved connection (never a password).
function prefillConnForm(c) {
  if (!$("conn_type")) return;
  $("conn_type").value = c.db_type || "sqlite";
  renderConnFields(c);
  if ($("conn_name")) $("conn_name").value = c.name || "";
}

// AP-10: connect directly from a saved connection chosen in the topbar.
// Passwordless connections (SQLite, or servers without auth) connect straight
// away; if the server rejects the empty password, fall back to the connection
// tab prefilled so the user can add it.
async function connectSaved(name) {
  const c = SAVED_CONNS.find((x) => x.name === name);
  if (!c) return;
  $("status").textContent = `verbinde mit „${name}“…`;
  try {
    const r = await postJSON("/api/connect", c);  // build_url ignores extra "name"
    setCurrentUrl(r.connection_url);
    await doConnect();
    syncConnSelectors(name);
  } catch (e) {
    $("status").textContent = "";
    openConnections();
    prefillConnForm(c);
    syncConnSelectors(name);
    alert(`„${name}“ konnte nicht direkt verbunden werden:\n${e.message}\n\n` +
          `Im Verbindungs-Tab ggf. das Passwort ergänzen und „Verbinden“ klicken.`);
  }
}

function openConnections() {
  const panel = ensureTab("connections", "Verbindungen", true);
  if (panel.dataset.built) return;
  panel.dataset.built = "1";
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
    `<div class="row"><button id="conn_connect" type="button">Verbinden</button>` +
    `<input id="conn_name" type="text" placeholder="Name zum Speichern">` +
    `<button id="conn_save" type="button">Speichern</button></div>` +
    `<p class="hint" id="conn_msg"></p></div>`;

  $("conn_type").addEventListener("change", () => renderConnFields());
  renderConnFields();
  $("conn_connect").addEventListener("click", async () => {
    $("conn_msg").textContent = "verbinde…";
    try {
      const r = await postJSON("/api/connect", formParams());
      setCurrentUrl(r.connection_url);
      await doConnect();
    } catch (e) { $("conn_msg").textContent = "Fehler: " + e.message; }
  });
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
  $("conn_load_saved").addEventListener("click", () => {
    const c = SAVED_CONNS.find((x) => x.name === $("conn_saved").value);
    if (!c) return;
    $("conn_type").value = c.db_type;
    renderConnFields(c);
    $("conn_name").value = c.name;
  });
  $("conn_delete_saved").addEventListener("click", async () => {
    const name = $("conn_saved").value;
    if (!name) return;
    await fetch("/api/connections", {
      method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    await refreshSavedConnections();
  });
  refreshSavedConnections();
}

// ===== Wiring =====
// "Verbinden" connects to the chosen saved connection (must be clicked actively;
// changing the dropdown only selects, it no longer auto-connects). Falls back to
// the hidden connection_url if nothing is selected.
$("btn_load").addEventListener("click", () => {
  const name = $("topbar_conn").value;
  if (name) connectSaved(name);
  else doConnect();
});
$("schema_select").addEventListener("change", (e) => {
  SELECTED_SCHEMA = e.target.value;
  doConnect();
});
$("uml_reset").addEventListener("click", clearSelectionAndCards);
$("include_implied").addEventListener("change", () => {
  if (SCHEMA.tables.length) drawGraph().catch((e) => alert(e.message));
});
$("graph_relayout").addEventListener("click", runGraphLayout);  // AP-13: re-roll layout

// AP-10: populate the topbar connection picker on initial load; preselect the
// bundled "Demo" connection by default (user still clicks "Verbinden").
refreshSavedConnections().then(() => {
  const tb = $("topbar_conn");
  if (tb && SAVED_CONNS.some((c) => c.name === "Demo")) tb.value = "Demo";
});

setCurrentUrl(connUrl());   // show the prefilled demo connection
renderSidebar();            // show Tools/Info even before connecting
setupSplitter();
setupLeftSplitter();        // AP-13: resizable sidebar width
setupObjectSearch();        // AP-13: object-browser name filter
setupZoomControl();         // AP-7: graph zoom slider
setupSqlCopy();             // AP-20: copy generated SELECT to clipboard
setupGraphAutofit();        // keep the graph centered + space-filling on resize

// Re-center and re-fit the graph whenever the window size changes, so it always
// maximizes the graph panel (splitter drags already re-fit on mouseup).
function setupGraphAutofit() {
  let timer = null;
  window.addEventListener("resize", () => {
    if (!CY) return;
    clearTimeout(timer);
    timer = setTimeout(() => { CY.resize(); CY.fit(undefined, GRAPH_FIT_PAD); }, 120);
  });
}

// AP-20: copy the generated SELECT to the clipboard via the icon in its corner.
function setupSqlCopy() {
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest ? e.target.closest("#sql_copy") : null;
    if (!btn) return;
    const sql = $("sql_out") ? $("sql_out").textContent : "";
    if (!sql.trim()) return;
    try {
      await navigator.clipboard.writeText(sql);
      btn.classList.add("copied");
      setTimeout(() => btn.classList.remove("copied"), 1200);
    } catch (err) { /* clipboard unavailable — ignore */ }
  });
}
