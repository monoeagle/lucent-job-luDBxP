"use strict";
let SCHEMA = { tables: [] };

// Operators the backend accepts (core/sqlgen.py _ALLOWED_OPS).
const OPERATORS = ["=", "!=", "<", ">", "<=", ">=", "LIKE"];

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

function tableOptions() {
  return SCHEMA.tables.map((t) => `<option>${t.name}</option>`).join("");
}

function columnOptions(tableName) {
  const t = SCHEMA.tables.find((x) => x.name === tableName);
  return (t ? t.columns : []).map((c) => `<option>${c}</option>`).join("");
}

function fillTableSelects() {
  for (const id of ["start_table", "target_table"]) {
    document.getElementById(id).innerHTML = tableOptions();
  }
  fillColumns("start_table", "start_col");
  fillColumns("target_table", "target_col");
}

function fillColumns(tableSel, colSel) {
  const tname = document.getElementById(tableSel).value;
  document.getElementById(colSel).innerHTML = columnOptions(tname);
}

// --- Filter rows ----------------------------------------------------------
function addFilterRow() {
  if (!SCHEMA.tables.length) return;
  const row = document.createElement("div");
  row.className = "filter-row";
  const firstTable = SCHEMA.tables[0].name;
  row.innerHTML =
    `<select class="f-table">${tableOptions()}</select>` +
    `<select class="f-col">${columnOptions(firstTable)}</select>` +
    `<select class="f-op">${OPERATORS.map((o) => `<option>${o}</option>`).join("")}</select>` +
    `<input class="f-val" type="text" placeholder="Wert">` +
    `<button type="button" class="f-del">✕</button>`;
  // Column list follows the chosen table.
  row.querySelector(".f-table").addEventListener("change", (ev) => {
    row.querySelector(".f-col").innerHTML = columnOptions(ev.target.value);
  });
  row.querySelector(".f-del").addEventListener("click", () => row.remove());
  document.getElementById("filters").appendChild(row);
}

function collectFilters() {
  const rows = document.querySelectorAll("#filters .filter-row");
  const filters = [];
  for (const row of rows) {
    const table = row.querySelector(".f-table").value;
    const column = row.querySelector(".f-col").value;
    const op = row.querySelector(".f-op").value;
    const value = row.querySelector(".f-val").value;
    // Skip incomplete rows (a missing value is not a filter).
    if (table && column && op && value !== "") {
      filters.push({ table, column, op, value });
    }
  }
  return filters;
}

// --- Wiring ---------------------------------------------------------------
document.getElementById("btn_load").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  try {
    SCHEMA = await postJSON("/api/schema", { connection_url: url });
    fillTableSelects();
    document.getElementById("filters").innerHTML = "";  // reset on new schema
    document.getElementById("builder").hidden = false;
  } catch (e) { alert(e.message); }
});

document.getElementById("start_table").addEventListener("change", () =>
  fillColumns("start_table", "start_col"));
document.getElementById("target_table").addEventListener("change", () =>
  fillColumns("target_table", "target_col"));

document.getElementById("btn_add_filter").addEventListener("click", addFilterRow);

document.getElementById("btn_build").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  const body = {
    connection_url: url,
    start: { table: start_table.value, column: start_col.value },
    target: { table: target_table.value, column: target_col.value },
    filters: collectFilters(),
  };
  try {
    const data = await postJSON("/api/joinpath", body);
    const list = document.getElementById("path_list");
    list.innerHTML = data.paths
      .map((p, i) => `<li><a href="#" data-i="${i}">${p.tables.join(" → ")}</a></li>`)
      .join("");
    const show = (i) => { document.getElementById("sql_out").textContent = data.paths[i].sql; };
    list.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", (ev) => { ev.preventDefault(); show(+a.dataset.i); }));
    show(0);
    document.getElementById("result").hidden = false;
  } catch (e) { alert(e.message); }
});
