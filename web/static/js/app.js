"use strict";
let SCHEMA = { tables: [] };

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

function fillTableSelects() {
  const opts = SCHEMA.tables.map((t) => `<option>${t.name}</option>`).join("");
  for (const id of ["start_table", "target_table"]) {
    document.getElementById(id).innerHTML = opts;
  }
  fillColumns("start_table", "start_col");
  fillColumns("target_table", "target_col");
}

function fillColumns(tableSel, colSel) {
  const tname = document.getElementById(tableSel).value;
  const t = SCHEMA.tables.find((x) => x.name === tname);
  document.getElementById(colSel).innerHTML =
    (t ? t.columns : []).map((c) => `<option>${c}</option>`).join("");
}

document.getElementById("btn_load").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  try {
    SCHEMA = await postJSON("/api/schema", { connection_url: url });
    fillTableSelects();
    document.getElementById("builder").hidden = false;
  } catch (e) { alert(e.message); }
});

document.getElementById("start_table").addEventListener("change", () =>
  fillColumns("start_table", "start_col"));
document.getElementById("target_table").addEventListener("change", () =>
  fillColumns("target_table", "target_col"));

document.getElementById("btn_build").addEventListener("click", async () => {
  const url = document.getElementById("connection_url").value;
  const body = {
    connection_url: url,
    start: { table: start_table.value, column: start_col.value },
    target: { table: target_table.value, column: target_col.value },
    filters: [],
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
