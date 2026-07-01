# Server-Demo-CMDB (MSSQL; Oracle-Adaption als Folge)

Zeigt im LucentTools-Tree alle reflektierbaren Objektkategorien (Tabellen, Views,
Trigger, Procedures, Functions, Sequences, Synonyms) — anders als die SQLite-Demo.

## MSSQL-Container (podman)
```bash
podman run -d --name mssql-luDBxP -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD='LucentTest2026' \
  -p 1433:1433 mcr.microsoft.com/mssql/server:2022-latest
```

## Seed einspielen
```bash
./venv/bin/python sample_data/seed_server_demo.py \
  'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/master?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```
Idempotent — mehrfach ausführbar.

## Aufgeräumter Tree: eigene Demo-DB (empfohlen)
Die `master`-DB enthält MSSQL-System-Prozeduren (`sp_MSrepl_startup` …), die sonst im
Routinen-Tree mit auftauchen. Für einen sauberen Demo-Tree eine eigene DB anlegen und
die URL darauf zeigen lassen (eine frische User-DB hat keine System-Procs):
```bash
# DB einmalig anlegen (z. B. via sqlcmd im Container):
podman exec -i mssql-luDBxP /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P 'LucentTest2026' -C \
  -Q "IF DB_ID('luDBxP_demo') IS NULL CREATE DATABASE luDBxP_demo"
# dann gegen die Demo-DB seeden + verbinden (…/luDBxP_demo statt …/master):
./venv/bin/python sample_data/seed_server_demo.py \
  'mssql+pyodbc://sa:LucentTest2026@127.0.0.1:1433/luDBxP_demo?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes'
```

## In der App verbinden
Verbindung mit der Seed-URL anlegen → der Tree zeigt alle 7 Kategorien; `vw_vm_labeled`
zeigt im Detail „Verwendet Routinen: fn_vm_label" (AP-66·S1).

## Oracle (AP-67·Oracle-Adaption)

Oracle hat kein portables Einzeldatei-Format — die Demo braucht eine laufende Instanz.

1. Container starten (login-freies Image):
   ```bash
   podman run -d --name oracle-luDBxP -p 1521:1521 \
     -e ORACLE_PASSWORD=LucentTest2026 -e APP_USER=demo -e APP_USER_PASSWORD=demo \
     docker.io/gvenzl/oracle-xe:21-slim-faststart
   ```
2. Demo einspielen (idempotent):
   ```bash
   ./venv/bin/python sample_data/seed_server_demo.py \
     'oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1'
   ```
3. In der App verbinden mit
   `oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1` — der Sidebar-Tree
   zeigt dann alle Oracle-Kategorien (Tabellen, View, Sequence, Materialized View,
   Trigger, Function, Procedure, Package, Synonym).
4. Live-Test (optional):
   ```bash
   LUCENT_ORACLE_TEST_URL='oracle+oracledb://demo:demo@localhost:1521/?service_name=XEPDB1' \
     ./venv/bin/python -m pytest tests/test_oracle_seed_integration.py
   ```

Hinweis: `CLUSTER` ist in Oracle reserviert; die Cluster-Tabelle heißt im Oracle-Demo `VMCluster`.
