"use strict";

let SCHEMA = { tables: [], views: [] };
let CY = null;  // Cytoscape instance for the schema graph
let SAVED_CONNS = [];  // saved connections (without passwords)
const OPERATORS = ["=", "!=", "<", ">", "<=", ">=", "LIKE",
                   "IS NULL", "IS NOT NULL", "IN", "BETWEEN"];
const DB_TYPES = [
  { v: "sqlite", label: "SQLite (Datei)" },
  { v: "postgresql", label: "PostgreSQL" },
  { v: "mysql", label: "MySQL / MariaDB" },
  { v: "mssql", label: "MS SQL Server" },
];
const PORT_DEFAULTS = { postgresql: 5432, mysql: 3306, mssql: 1433 };

// ===== Graph selection state (AP-1: interactive join-path selection) =====
let GRAPH_SEL = { source: null, target: null };

// Padding (px) around the graph's bounding box on fit — small so the graph
// fills the panel and stays centered after layout/resize.
const GRAPH_FIT_PAD = 16;

// ===== Join-builder state (AP-6: result refresh + row-count selection) =====
let JB_LAST = null;     // { body, paths } from the last successful build
let JB_PATH_IDX = 0;    // currently selected path index

const $ = (id) => document.getElementById(id);

// The real URL (with password) lives in a hidden field; show a masked form.
function maskUrl(url) {
  return url.replace(/(:\/\/[^:/@]+:)[^@]*@/, "$1***@");
}
function setCurrentUrl(url) {
  $("connection_url").value = url;
  $("current_conn").textContent = url ? maskUrl(url) : "(keine Verbindung)";
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

async function postJSON(url, body) {
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
    `<li data-action="joinbuilder">Join-Builder</li></ul>` +
    `<h3>Tabellen (${SCHEMA.tables.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.tables, "table")}</ul>` +
    `<h3>Views (${SCHEMA.views.length})</h3>` +
    `<ul class="objlist">${objList(SCHEMA.views, "view")}</ul>` +
    `<div class="sidebar-bottom"><h3>Info</h3>` +
    `<ul class="objlist"><li data-action="info">Übersicht</li></ul></div>`;
  $("objects").querySelectorAll("li").forEach((li) => {
    li.addEventListener("click", () => {
      if (li.dataset.action === "joinbuilder") openJoinBuilder();
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
    return `<tr><td>${esc(c.name)}${pk}</td><td>${esc(c.type)}</td></tr>`;
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
    defHtml = `<h2>Tabelle: ${esc(t.name)}</h2>` +
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

// ===== Join builder tab =====
function openJoinBuilder() {
  const panel = ensureTab("joinbuilder", "Join-Builder", true);
  if (panel.dataset.built) return;
  panel.dataset.built = "1";
  panel.innerHTML =
    `<div class="joinbuilder">` +
    `<div class="row"><label>Start</label>` +
    `<select id="start_table"></select> . <select id="start_col"></select></div>` +
    `<div class="row"><label>Ziel</label>` +
    `<select id="target_table"></select> . <select id="target_col"></select></div>` +
    `<div class="filters" id="filters"></div>` +
    `<div class="filters" id="order_bys"></div>` +
    `<div class="filters" id="extra_cols"></div>` +
    `<div class="row jb-actions">` +
    `<button id="btn_add_filter" title="Filterbedingung (mit UND verknüpft)">Filter +</button>` +
    `<button id="btn_add_orderby" title="Sortierungsspalte hinzufügen">Sortierung +</button>` +
    `<button id="btn_add_col" title="Weitere SELECT-Spalte hinzufügen">Spalten +</button></div>` +
    `<div class="row jb-options">` +
    `<label class="jb-check"><input type="checkbox" id="jb_distinct"> DISTINCT</label>` +
    `<label class="jb-limit">LIMIT <input id="jb_limit" type="number" min="1" placeholder="–"></label>` +
    `<label class="jb-dialect" title="SQL-Dialekt der generierten Abfrage">Dialekt ` +
    `<select id="jb_dialect">` +
    `<option value="sqlite">SQLite</option>` +
    `<option value="postgresql">PostgreSQL</option>` +
    `<option value="mysql">MySQL</option>` +
    `<option value="mssql">MSSQL</option>` +
    `<option value="oracle">Oracle</option></select></label>` +
    `<button id="btn_build">Join-Pfad bauen</button></div>` +
    `<ul class="path_list" id="path_list"></ul>` +
    `<div class="sql-wrap"><button id="sql_copy" class="sql-copy" type="button" ` +
    `title="SELECT in die Zwischenablage kopieren" aria-label="SELECT kopieren">` +
    `<svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" ` +
    `stroke-width="1.4"><rect x="4" y="3" width="9" height="11" rx="1.5"/>` +
    `<path d="M6 3V2.2A1.2 1.2 0 0 1 7.2 1h2.6A1.2 1.2 0 0 1 11 2.2V3"/></svg></button>` +
    `<pre class="sql_out" id="sql_out"></pre></div>` +
    `<div class="row jb-result-bar" id="jb_result_bar" style="display:none">` +
    `<label>Zeilen</label>` +
    `<select id="jb_rows">` +
    `<option value="200">200</option>` +
    `<option value="400">400</option>` +
    `<option value="0">Alle</option></select>` +
    `<button id="jb_refresh" title="Ausgabe mit aktuellen Sortierungen/Spalten neu berechnen">Aktualisieren</button>` +
    `<span id="jb_rows_info" class="hint"></span></div>` +
    `<div id="join_result"></div></div>`;
  $("start_table").addEventListener("change", () => fillCols("start_table", "start_col"));
  $("target_table").addEventListener("change", () => fillCols("target_table", "target_col"));
  $("btn_add_filter").addEventListener("click", addFilterRow);
  $("btn_add_orderby").addEventListener("click", addOrderByRow);
  $("btn_add_col").addEventListener("click", addColRow);
  $("btn_build").addEventListener("click", () => runBuild());
  // AP-6: refresh re-reads the form (new sort/columns) and keeps the chosen path;
  // changing the row count only re-fetches the current path (path is unaffected).
  $("jb_refresh").addEventListener("click", () => runBuild(true));
  $("jb_rows").addEventListener("change", () => renderJoinResult(JB_PATH_IDX));
  // AP-29: default the dialect to the connected backend; re-render SQL on change.
  $("jb_dialect").value = dialectFromUrl(connUrl());
  $("jb_dialect").addEventListener("change", () => runBuild(true));
  if (SCHEMA.tables.length) refillJoinBuilder();
}

function fillCols(tableSel, colSel) {
  const t = tableByName($(tableSel).value);
  $(colSel).innerHTML = optionList(t ? t.columns.map((c) => c.name) : []);
}

function refillJoinBuilder() {
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
  if ($("jb_distinct")) $("jb_distinct").checked = false;
  if ($("jb_limit")) $("jb_limit").value = "";
  if ($("jb_result_bar")) $("jb_result_bar").style.display = "none";
  if ($("jb_rows_info")) $("jb_rows_info").textContent = "";
  JB_LAST = null;
  JB_PATH_IDX = 0;
}

// Render the value input(s) for a filter row based on the selected operator.
function _updateFilterValueField(row) {
  const op = row.querySelector(".f-op").value;
  const wrap = row.querySelector(".f-val-wrap");
  if (op === "IS NULL" || op === "IS NOT NULL") {
    wrap.innerHTML = "";
  } else if (op === "BETWEEN") {
    wrap.innerHTML =
      `<input class="f-val-lo" type="text" placeholder="von">` +
      `<input class="f-val-hi" type="text" placeholder="bis">`;
  } else if (op === "IN") {
    wrap.innerHTML =
      `<input class="f-val" type="text" placeholder="Wert1, Wert2, …">`;
  } else {
    wrap.innerHTML = `<input class="f-val" type="text" placeholder="Wert">`;
  }
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
  row.querySelector(".f-table").addEventListener("change", fillFcol);
  row.querySelector(".f-op").addEventListener("change", () => _updateFilterValueField(row));
  row.querySelector(".f-del").addEventListener("click", () => row.remove());
  _updateFilterValueField(row);  // render initial value field for default op "="
  $("filters").appendChild(row);
}

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
  $("order_bys").appendChild(row);
}

function collectOrderBy() {
  const out = [];
  document.querySelectorAll("#order_bys .orderby-row").forEach((row) => {
    const table = row.querySelector(".ob-table").value;
    const column = row.querySelector(".ob-col").value;
    const dir = row.querySelector(".ob-dir").value;
    if (table && column && dir) out.push({ table, column, dir });
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
    `<button type="button" class="c-del">✕</button>`;
  const fillCcol = () => {
    const t = tableByName(row.querySelector(".c-table").value);
    row.querySelector(".c-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillCcol();
  row.querySelector(".c-table").addEventListener("change", fillCcol);
  row.querySelector(".c-del").addEventListener("click", () => row.remove());
  $("extra_cols").appendChild(row);
}

function collectExtraSelects() {
  const out = [];
  document.querySelectorAll("#extra_cols .col-row").forEach((row) => {
    const table = row.querySelector(".c-table").value;
    const column = row.querySelector(".c-col").value;
    if (table && column) out.push({ table, column });
  });
  return out;
}

// Read the full join-builder form into a /api/joinpath request body.
function collectJoinBody() {
  const limitRaw = $("jb_limit") ? $("jb_limit").value.trim() : "";
  return {
    connection_url: connUrl(),
    start: { table: $("start_table").value, column: $("start_col").value },
    target: { table: $("target_table").value, column: $("target_col").value },
    filters: collectFilters(),
    extra_selects: collectExtraSelects(),
    include_implied: includeImplied(),
    distinct: $("jb_distinct") ? $("jb_distinct").checked : false,
    order_by: collectOrderBy(),
    limit: limitRaw !== "" ? parseInt(limitRaw, 10) : null,
    dialect: $("jb_dialect") ? $("jb_dialect").value : "sqlite",
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
function jbSelectedMaxRows() {
  const sel = $("jb_rows");
  if (!sel) return 200;
  return sel.value === "0" ? null : parseInt(sel.value, 10);
}

// Execute the SELECT for path `i` and render its rows into #join_result.
async function renderJoinResult(i) {
  if (!JB_LAST || !JB_LAST.paths[i]) return;
  JB_PATH_IDX = i;
  $("sql_out").textContent = JB_LAST.paths[i].sql;
  highlightPath(JB_LAST.paths[i].edges || []);
  const resultEl = $("join_result");
  if (!resultEl) return;
  resultEl.innerHTML = "<p class='hint'>lädt…</p>";
  const info = $("jb_rows_info");
  if (info) info.textContent = "";
  try {
    const runBody = Object.assign({}, JB_LAST.body,
      { path_index: i, max_rows: jbSelectedMaxRows() });
    const res = await postJSON("/api/joinpath/run", runBody);
    if (!res.rows.length) {
      resultEl.innerHTML = "<p class='hint'>keine Ergebniszeilen</p>";
      return;
    }
    const thead = res.columns.map((c) => `<th>${esc(c)}</th>`).join("");
    const tbody = res.rows.map((r) =>
      "<tr>" + r.map((v) =>
        `<td>${v === null ? "<i>NULL</i>" : esc(v)}</td>`).join("") + "</tr>"
    ).join("");
    resultEl.innerHTML =
      `<table class="cols"><thead><tr>${thead}</tr></thead>` +
      `<tbody>${tbody}</tbody></table>`;
    if (info) {
      const cap = res.row_cap || res.rows.length;
      info.textContent = res.rows.length >= cap
        ? `${res.rows.length} Zeilen (begrenzt auf ${cap})`
        : `${res.rows.length} Zeilen`;
    }
  } catch (e) {
    resultEl.innerHTML = `<p class='hint'>Fehler: ${esc(e.message)}</p>`;
  }
}

// Build join paths from the current form. `preserveIndex` keeps the selected
// path (used by "Aktualisieren" after a sort/column change); a fresh build
// from "Join-Pfad bauen" resets to the first path.
async function runBuild(preserveIndex = false) {
  const body = collectJoinBody();
  try {
    const data = await postJSON("/api/joinpath", body);
    JB_LAST = { body, paths: data.paths };
    const prev = JB_PATH_IDX;
    JB_PATH_IDX = preserveIndex && prev < data.paths.length ? prev : 0;
    const list = $("path_list");
    list.innerHTML = data.paths.map((p, i) => {
      const warn = (p.warnings && p.warnings.length)
        ? `<div class="path-warn">⚠ ${p.warnings.map(esc).join(" ")}</div>`
        : "";
      return `<li><a href="#" data-i="${i}">${p.tables.map(esc).join(" → ")}</a>${warn}</li>`;
    }).join("");
    list.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); renderJoinResult(+a.dataset.i); }));
    const bar = $("jb_result_bar");
    if (data.paths.length) {
      if (bar) bar.style.display = "";
      renderJoinResult(JB_PATH_IDX);
    } else {
      if (bar) bar.style.display = "none";
      $("sql_out").textContent = "";
      $("join_result").innerHTML = "";
    }
  } catch (e) { alert(e.message); }
}

// ===== UML card area (AP-1) =====
function showUmlCard(tableName) {
  const t = tableByName(tableName);
  if (!t) return;
  const cards = $("uml_cards");
  if (!cards) return;

  // If card already exists, move it to the front
  let card = cards.querySelector(`.uml-card[data-table="${CSS.escape(tableName)}"]`);
  if (card) { cards.insertBefore(card, cards.firstChild); return; }

  card = document.createElement("div");
  card.className = "uml-card";
  card.dataset.table = tableName;

  const colsHtml = t.columns.map((c) => {
    const pk = c.pk ? ` <span class="badge">PK</span>` : "";
    return `<div class="uml-col" data-table="${esc(tableName)}" data-col="${esc(c.name)}">${esc(c.name)}${pk}<span class="uml-col-type">${esc(c.type)}</span></div>`;
  }).join("");

  card.innerHTML = `<div class="uml-card-head">${esc(tableName)}</div>${colsHtml}`;
  card.querySelectorAll(".uml-col").forEach((row) => {
    row.addEventListener("click", () => selectColumn(row.dataset.table, row.dataset.col));
  });
  cards.insertBefore(card, cards.firstChild);
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
  openJoinBuilder();
  $("start_table").value = src.table;
  fillCols("start_table", "start_col");
  $("start_col").value = src.column;
  $("target_table").value = tgt.table;
  fillCols("target_table", "target_col");
  $("target_col").value = tgt.column;
  activateTab("joinbuilder");
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
  if (CY) CY.elements().removeClass("hl");        // clear highlighted join path
  if ($("uml_cards")) $("uml_cards").innerHTML = "";  // close the cards below
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
      { selector: "edge.hl", style: { "line-color": "#E0532E", width: 4 } },
      { selector: "node.sel-source", style: {
        "border-width": 4, "border-color": "#1e7e34" } },
      { selector: "node.sel-target", style: {
        "border-width": 4, "border-color": "#c0392b" } },
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

function highlightPath(edges) {
  if (!CY) return;
  CY.elements().removeClass("hl");
  const nodes = new Set();
  for (const [a, b] of edges) {
    nodes.add(a);
    nodes.add(b);
    CY.edges().forEach((e) => {
      const s = e.source().id(), t = e.target().id();
      if ((s === a && t === b) || (s === b && t === a)) e.addClass("hl");
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

// ===== Connect with the current URL (hidden field) =====
async function doConnect() {
  try {
    SCHEMA = await postJSON("/api/schema", { connection_url: connUrl() });
    document.querySelectorAll(".tab").forEach((t) => closeTab(t.dataset.tab));
    renderSidebar();
    openJoinBuilder();
    refillJoinBuilder();
    activateTab("joinbuilder");
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
    `value="${esc(port)}"></div>` +
    `<div class="row"><label>Datenbank</label><input id="cf_database" type="text" ` +
    `value="${esc(c.database || "")}"></div>` +
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
    database: $("cf_database").value, user: $("cf_user").value,
    password: $("cf_password").value,
  };
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
$("btn_load").addEventListener("click", doConnect);
$("btn_connections").addEventListener("click", openConnections);
$("uml_reset").addEventListener("click", clearSelectionAndCards);
$("include_implied").addEventListener("change", () => {
  if (SCHEMA.tables.length) drawGraph().catch((e) => alert(e.message));
});
$("topbar_conn").addEventListener("change", (e) => {
  if (e.target.value) connectSaved(e.target.value);
});
$("graph_relayout").addEventListener("click", runGraphLayout);  // AP-13: re-roll layout

// AP-10: populate the topbar connection picker on initial load.
refreshSavedConnections();

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
