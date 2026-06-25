"use strict";

let SCHEMA = { tables: [], views: [] };
let CY = null;  // Cytoscape instance for the schema graph
const OPERATORS = ["=", "!=", "<", ">", "<=", ">=", "LIKE"];

const $ = (id) => document.getElementById(id);

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
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

function closeDetailTabs() {
  document.querySelectorAll(".tab").forEach((t) => {
    if (t.dataset.tab !== "joinbuilder") closeTab(t.dataset.tab);
  });
}

// ===== Object browser (sidebar) =====
function renderSidebar() {
  const list = (items, kind) => items.map((o) =>
    `<li data-kind="${kind}" data-name="${o.name}">${o.name}</li>`).join("");
  $("objects").innerHTML =
    `<h3>Tabellen (${SCHEMA.tables.length})</h3>` +
    `<ul class="objlist">${list(SCHEMA.tables, "table")}</ul>` +
    `<h3>Views (${SCHEMA.views.length})</h3>` +
    `<ul class="objlist">${list(SCHEMA.views, "view")}</ul>`;
  $("objects").querySelectorAll("li").forEach((li) =>
    li.addEventListener("click", () => openDetail(li.dataset.kind, li.dataset.name)));
}

// ===== Detail tab (table or view) =====
function colRows(columns, withPk) {
  return columns.map((c) => {
    const pk = withPk && c.pk ? ` <span class="badge">PK</span>` : "";
    return `<tr><td>${c.name}${pk}</td><td>${c.type}</td></tr>`;
  }).join("");
}

function openDetail(kind, name) {
  const id = `det:${kind}:${name}`;
  const panel = ensureTab(id, name, true);
  if (panel.dataset.built) return;
  panel.dataset.built = "1";

  if (kind === "table") {
    const t = tableByName(name);
    const fks = t.foreign_keys.length
      ? "<ul>" + t.foreign_keys.map((f) =>
          `<li>${f.column} → ${f.ref_table}.${f.ref_column}</li>`).join("") + "</ul>"
      : "<p class='hint'>keine Foreign Keys</p>";
    panel.innerHTML =
      `<div class="detail"><h2>Tabelle: ${t.name}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(t.columns, true)}</tbody></table>` +
      `<h3>Foreign Keys</h3>${fks}</div>`;
  } else {
    const v = SCHEMA.views.find((x) => x.name === name);
    panel.innerHTML =
      `<div class="detail"><h2>View: ${v.name}</h2>` +
      `<table class="cols"><thead><tr><th>Spalte</th><th>Typ</th></tr></thead>` +
      `<tbody>${colRows(v.columns, false)}</tbody></table>` +
      `<h3>Definition</h3><pre class="viewdef"></pre></div>`;
    panel.querySelector(".viewdef").textContent = v.definition || "(keine Definition)";
  }
}

// ===== Join builder tab =====
function buildJoinBuilder() {
  const panel = ensureTab("joinbuilder", "Join-Builder", false);
  panel.innerHTML =
    `<div class="joinbuilder">` +
    `<div class="row"><label>Start</label>` +
    `<select id="start_table"></select> . <select id="start_col"></select></div>` +
    `<div class="row"><label>Ziel</label>` +
    `<select id="target_table"></select> . <select id="target_col"></select></div>` +
    `<div class="filters" id="filters"></div>` +
    `<div class="row">` +
    `<button id="btn_add_filter" title="Filterbedingung (mit UND verknüpft)">Filter +</button>` +
    `<button id="btn_build">Join-Pfad bauen</button></div>` +
    `<ul class="path_list" id="path_list"></ul>` +
    `<pre class="sql_out" id="sql_out"></pre></div>`;

  $("start_table").addEventListener("change", () => fillCols("start_table", "start_col"));
  $("target_table").addEventListener("change", () => fillCols("target_table", "target_col"));
  $("btn_add_filter").addEventListener("click", addFilterRow);
  $("btn_build").addEventListener("click", runBuild);
}

function fillCols(tableSel, colSel) {
  const t = tableByName($(tableSel).value);
  $(colSel).innerHTML = optionList(t ? t.columns.map((c) => c.name) : []);
}

function refillJoinBuilder() {
  const names = SCHEMA.tables.map((t) => t.name);
  $("start_table").innerHTML = optionList(names);
  $("target_table").innerHTML = optionList(names);
  fillCols("start_table", "start_col");
  fillCols("target_table", "target_col");
  $("filters").innerHTML = "";
  $("path_list").innerHTML = "";
  $("sql_out").textContent = "";
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
    `<input class="f-val" type="text" placeholder="Wert">` +
    `<button type="button" class="f-del">✕</button>`;
  const fillFcol = () => {
    const t = tableByName(row.querySelector(".f-table").value);
    row.querySelector(".f-col").innerHTML =
      optionList(t ? t.columns.map((c) => c.name) : []);
  };
  fillFcol();
  row.querySelector(".f-table").addEventListener("change", fillFcol);
  row.querySelector(".f-del").addEventListener("click", () => row.remove());
  $("filters").appendChild(row);
}

function collectFilters() {
  const out = [];
  document.querySelectorAll("#filters .filter-row").forEach((row) => {
    const table = row.querySelector(".f-table").value;
    const column = row.querySelector(".f-col").value;
    const op = row.querySelector(".f-op").value;
    const value = row.querySelector(".f-val").value;
    if (table && column && op && value !== "") out.push({ table, column, op, value });
  });
  return out;
}

async function runBuild() {
  const body = {
    connection_url: connUrl(),
    start: { table: $("start_table").value, column: $("start_col").value },
    target: { table: $("target_table").value, column: $("target_col").value },
    filters: collectFilters(),
    include_implied: includeImplied(),
  };
  try {
    const data = await postJSON("/api/joinpath", body);
    const list = $("path_list");
    list.innerHTML = data.paths.map((p, i) =>
      `<li><a href="#" data-i="${i}">${p.tables.join(" → ")}</a></li>`).join("");
    const show = (i) => {
      $("sql_out").textContent = data.paths[i].sql;
      highlightPath(data.paths[i].edges || []);
    };
    list.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); show(+a.dataset.i); }));
    if (data.paths.length) show(0);
  } catch (e) { alert(e.message); }
}

// ===== Schema graph =====
async function drawGraph() {
  const g = await postJSON("/api/graph", {
    connection_url: connUrl(), include_implied: includeImplied(),
  });
  if (CY) CY.destroy();
  const elements = [
    ...g.nodes.map((n) => ({ data: { id: n.id } })),
    ...g.edges.map((e) => ({
      data: { source: e.source, target: e.target, implied: !!e.implied },
    })),
  ];
  CY = cytoscape({
    container: $("graph"),
    elements,
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
    ],
  });
  const layout = CY.layout({
    name: "cose", animate: false, padding: 24, randomize: true,
    nodeRepulsion: 16000, idealEdgeLength: 110, nodeOverlap: 28, componentSpacing: 120,
  });
  layout.one("layoutstop", () => CY.fit(undefined, 24));
  layout.run();
  window.CY = CY;  // expose for browser-console debugging and e2e checks
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

// ===== Wiring =====
$("btn_load").addEventListener("click", async () => {
  try {
    SCHEMA = await postJSON("/api/schema", { connection_url: connUrl() });
    closeDetailTabs();
    renderSidebar();
    refillJoinBuilder();
    activateTab("joinbuilder");
    await drawGraph();
    $("status").textContent =
      `verbunden — ${SCHEMA.tables.length} Tabellen, ${SCHEMA.views.length} Views`;
  } catch (e) {
    $("status").textContent = "";
    alert(e.message);
  }
});

$("include_implied").addEventListener("change", () => {
  if (SCHEMA.tables.length) drawGraph().catch((e) => alert(e.message));
});

buildJoinBuilder();  // create the (empty) join-builder tab on load
