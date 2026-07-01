# Changelog

## [0.64.0] — 2026-07-01

### Hinzugefügt
- **Oracle-Server-Demo-CMDB-Seeder (AP-67·Oracle-Adaption):** Der `oracle`-Zweig von
  `sample_data/seed_server_demo.py` (bisher ein Stub) baut jetzt dieselbe kompakte 5-Tabellen-CMDB
  wie der MSSQL-Seeder plus alle Oracle-spezifischen Objektkategorien — `SEQUENCE`, `MATERIALIZED
  VIEW`, `PACKAGE` (Spec + Body), standalone `FUNCTION` und `PROCEDURE`, `SYNONYM`, PL/SQL-`TRIGGER`
  und eine `VIEW`, die die Function aufruft (zeigt den AP-66·S1 View→Routine-Link). Damit ist jede
  Oracle-Sidebar-Kategorie im Tree sichtbar. Oracle-Besonderheiten: Drop je Objekt via `BEGIN
  EXECUTE IMMEDIATE 'DROP …'; EXCEPTION WHEN OTHERS THEN NULL; END;` (kein `IF EXISTS`), `CREATE OR
  REPLACE` für PL/SQL-Objekte, einzeilige INSERTs, und — weil `CLUSTER` in Oracle reserviert ist —
  heißt die Cluster-Tabelle `VMCluster`. Ein skip-guardeter Live-Integrationstest
  `tests/test_oracle_seed_integration.py` (`LUCENT_ORACLE_TEST_URL`) seedet und prüft, dass jede
  Kategorie reflektiert; `sample_data/server-demo-README.md` dokumentiert den podman-Oracle-XE-Bring-up.
  **Live gegen Oracle 21c XE verifiziert** (alle Kategorien reflektieren, inkl. View→Function).
  Externes Setup-Skript — das read-only-Werkzeug führt es nie aus.

## [0.63.0] — 2026-07-01

### Hinzugefügt
- **Analyzer-Lints mit Zeilenbezug + Klick-Lokalisierung (AP-65·C):** Jede knoten-spezifische
  Warnung und jeder Optimierungs-Vorschlag (SELECT *, LIKE mit führendem '%', Funktion-auf-Spalte,
  verdächtiger Alias, kartesischer Join, unbekannte Tabelle/Spalte, OR in WHERE, Unterabfrage in
  WHERE) nennt jetzt die zugehörige **Zeile**. Ein neuer reiner Helfer
  `core/sqlanalyze.py::_node_line(node, sql)` leitet die 1-basierte Zeile aus dem frühesten
  positionierten sqlglot-Nachfahren ab (`.meta['start']`); `AnalysisWarning`/`AnalysisSuggestion`
  erhalten ein Feld `line: int | None` (Statement-Ebene wie WRITE_STATEMENT/NO_WHERE bleibt `None`).
  `/api/analyze` serialisiert `line`; die UI stellt solchen Meldungen „Zeile N:" voran und macht sie
  **anklickbar** — ein Klick markiert die Zeile im Eingabefeld über den AP-65·B-Gutter
  (`setErrorLine`). Read-only, NO-CDN, kein neues Core-Modul.

## [0.62.0] — 2026-07-01

### Hinzugefügt
- **Analyzer-Zeilennummern-Gutter + Fehlerzeilen-Highlight (AP-65·B):** Das Eingabefeld des
  SQL-Analyzers hat jetzt eine scroll-synchrone Zeilennummern-Spalte, und bei einem Parse-Fehler
  wird die Fehlerzeile (`parse_error_line`) im Feld farbig hinterlegt. Umsetzung als reiner
  Frontend-3-Schicht-Editor (`web/static/js/app.js::attachLineGutter`): Zeilennummern-Gutter,
  scroll-synchrone Backdrop-Ebene mit einer Zeile je logischer Textzeile (die Fehlerzeile trägt
  `.an-line-error`) und die transparente Textarea (`wrap="off"` → 1 logische Zeile = 1 visuelle
  Zeile) darüber, die einziger Wert-Träger bleibt. `openAnalyzer` verdrahtet sie (`panel._gutter`),
  `renderAnalyzeResult` ruft `setErrorLine(res.parse_error_line)` (wird bei erfolgreichem Parse oder
  jeder Eingabe gelöscht). NO-CDN (keine Editor-Lib), read-only, kein Backend-Change. Das Eingabefeld
  bleibt vertikal verstellbar.

## [0.61.0] — 2026-07-01

### Geändert
- **Analyzer zeigt bei nicht geschlossenem Anführungszeichen die echte Fehlerzeile
  (AP-65·A-Härtung 2):** Ein neuer reiner Helfer `core/sqlanalyze.py::_odd_quote_line(sql,
  quote_char)` findet die einzige Zeile mit **ungerader** Anzahl des offenen Quote-Zeichens —
  das ist die tatsächliche Fehlerzeile. Weicht sie von der am Eingabe-Ende offenen Zeile ab,
  leitet `_parse_error_location` die gemeldete Position dorthin um — **ohne Spalte/Markierung**
  (ein *fehlendes* Quote hat keine exakte Position) und mit deutschem Hinweis, der die Zeile
  nennt. Fällt die Ungerade-Zeile mit der Eingabe-Ende-Zeile zusammen oder ist die Zählung
  mehrdeutig (0 oder ≥2 ungerade Zeilen, z. B. legitimer mehrzeiliger String), bleibt das
  bisherige Eingabe-Ende-Verhalten unverändert. Die Analyzer-UI lässt „, Spalte N" im
  Fehler-Kopf weg, wenn keine Spalte vorliegt. Read-only, kein neues Core-Modul, voll CI-testbar.

## [0.60.0] — 2026-06-30

### Hinzugefügt
- **MSSQL-Synonyme werden jetzt reflektiert (AP-67·MSSQL-Grundlage):** `_reflect_synonyms` in
  `core/loaders/sqlalchemy_loader.py` erhält einen MSSQL-Zweig (`sys.synonyms`); Synonyme waren
  bisher nur für Oracle (`all_synonyms`) reflektiert. Ein neues idempotentes SQLAlchemy-Seeder-Skript
  `sample_data/seed_server_demo.py` baut eine kompakte 5-Tabellen-CMDB plus alle MSSQL-spezifischen
  Objektkategorien (Sequence, Function, Procedure, Trigger, eine View die die Function aufruft,
  Synonym) — MSSQL-first, strukturiert für eine spätere Oracle-Adaption; externes Setup-Skript,
  das das read-only-Werkzeug nicht ausführt. `sample_data/server-demo-README.md` dokumentiert den
  Bring-up. Ein neuer skip-guardeter MSSQL-Integrationstest verifiziert alle 7 reflektierbaren
  Objektkategorien inkl. AP-66·S1 View→Routine-Verknüpfung, live gegen einen MSSQL-Container.

### Behoben
- **Doku: MSSQL-Sequenzen wurden fälschlich als leer behauptet:** Die Projektdoku behauptete,
  `get_sequence_names` liefere für MSSQL leere Ergebnisse (`„SQLite/MSSQL → leer"`); MSSQL-Sequenzen
  werden über `get_sequence_names` **tatsächlich reflektiert**. In CLAUDE.md, architektur.md und
  datenmodell.md korrigiert.

## [0.59.0] — 2026-06-30

### Behoben
- **Nicht geschlossenes/verschobenes Anführungszeichen (TokenError) zeigt jetzt eine Position und einen ehrlichen Hinweis (AP-65·A-Härtung):**
  Bisher verbrauchte ein fehlendes `"` in einem mehrzeiligen Statement sqlglot bis zum EOF; der
  Analyzer zeigte keine Position. Ein neuer reiner Scanner-Helfer `_unclosed_quote_offset(sql)` in
  `core/sqlanalyze.py` lokalisiert das am Eingabe-Ende offen gebliebene Anführungszeichen. Der
  Analyzer zeigt jetzt Zeile/Spalte des nicht geschlossenen Anführungszeichens, markiert es im
  Kontext-Ausschnitt und fügt einen ehrlichen Hinweis hinzu: Bei verschobenen Anführungszeichen
  kann die eigentliche Ursache früher im Statement liegen (sqlglot kann sie nicht exakt benennen).
  `AnalysisResult` erhält zwei neue abschließende Felder: `parse_error_highlight_pos: int`
  (kontextrelativierter Index des markierten Tokens, ersetzt die alte `indexOf`-Erstvorkommens-Logik)
  und `parse_error_hint: str` (optionaler Hinweis-Text, der unterhalb des Ausschnitts erscheint,
  wenn sqlglots Position nur annähernd ist). `/api/analyze` serialisiert beide Felder. Die Analyzer-UI
  markiert über den Index und zeigt den Hinweis wenn vorhanden. Read-only — keine Autokorrektur.
  Vollständig CI-testbar (kein DB-Zugang nötig). Kein neues Core-Modul — `sqlanalyze.py` existierte bereits.

## [0.58.0] — 2026-06-29

### Hinzugefügt
- **SQL-Analyzer zeigt jetzt Parse-Fehler-Position — Zeile, Spalte und markiertes Token (AP-65·A):**
  Neuer Helfer `_parse_error_location(exc, sql)` in `core/sqlanalyze.py` extrahiert strukturierte
  Positionsinformationen aus sqlglot-Fehlern. `ParseError` wird über sqlglots `.errors[0]`
  (Zeile/Spalte/Kontext) aufgelöst; `TokenError` (z. B. nicht geschlossenes String-Literal)
  leitet die Position best-effort aus dem konsumierten Präfix in der Fehlermeldung ab.
  `AnalysisResult` erhält vier abschließende Felder: `parse_error_line: int | None`,
  `parse_error_col: int | None`, `parse_error_context: str` (Ausschnitt rund um das
  fehlerhafte Token) und `parse_error_highlight: str` (das fehlerhafte Token zum Markieren).
  `/api/analyze` serialisiert alle vier Felder. Im UI zeigt der Analyzer **„Parse-Fehler in
  Zeile N, Spalte M:"** plus den Kontext-Ausschnitt mit dem fehlerhaften Token in einem roten
  `.an-err-mark`-Span; ist keine Position verfügbar, fällt es auf die bisherige Zeichenketten-
  Darstellung zurück. Read-only — keine Autokorrektur. Stufe B (Zeilennummern-Gutter) und
  C (Lints mit Zeilenbezug) bleiben Backlog.

## [0.57.0] — 2026-06-29

### Hinzugefügt
- **Views zeigen jetzt, welche Routinen sie referenzieren (AP-66·Stufe 1):**
  Neues reines Modul `core/viewdeps.py::referenced_routines(definition, known_routine_names, dialect)`
  parst den View-SQL-Definitionstext via sqlglot, gleicht Funktionsaufruf-Namen (inkl. Oracle-Package-
  Qualifier) gegen den bereits reflektierten `schema.routines`-Set ab und gibt nur bestätigte Treffer
  zurück — eingebaute SQL-Funktionen werden ausgeschlossen. Das `View`-Model erhält ein abschließendes
  Feld `routines: tuple[str, ...] = ()`; Materialized Views reusen dasselbe Shape. Der Loader befüllt
  es für Views + Materialized Views (reflektiert Routinen einmalig vor der View-Schleife). `/api/schema`
  trägt `"routines": [...]` auf jedem View- und Matview-Eintrag. Im UI zeigt das View-/Matview-Detail
  einen Abschnitt **„Verwendet Routinen"**, wenn Routinen-Referenzen vorhanden sind; in der Sidebar
  erscheint ein **`ƒ`**-Badge bei Views, die Routinen verwenden. Migrations-relevantes Signal: Views,
  die Routinen aufrufen, sind nicht über reine Join/FK-Lineage migrierbar. Vollständig CI-testbar
  (sqlglot, keine DB nötig). Read-only — keine Routinen-Ausführung.

## [0.56.0] — 2026-06-29

### Hinzugefügt
- **Trigger-Reflektion auf PostgreSQL, Oracle und MS SQL Server erweitert (AP-63·Trigger-Fast-Follow):**
  `_reflect_triggers` in `core/loaders/sqlalchemy_loader.py` nimmt jetzt `(engine, schema)` entgegen und
  nutzt Pro-Dialekt-Katalog-SQL — **PostgreSQL** via `pg_trigger` + `pg_get_triggerdef`
  (`NOT tgisinternal`); **Oracle** via `all_triggers` (`base_object_type='TABLE'`) +
  `dbms_metadata.get_ddl`; **MSSQL** via `sys.triggers` + `sys.sql_modules`
  (`is_ms_shipped=0`). Nur Tabellen-/DML-Trigger werden reflektiert. Das `Trigger`-Model, die
  `/api/schema`-Serialisierung und die JS-Trigger-Sidebar-Kategorie sind unverändert (AP-63·S2,
  v0.53.0) — Trigger erscheinen jetzt einfach auch für die neuen Dialekte. MSSQL gegen
  Live-SQL-Server-2022 verifiziert; PG und Oracle sind skip-guarded Integrationstests. SQLite-Reflektion
  (via `sqlite_master`) bleibt unverändert.

## [0.55.1] — 2026-06-29

### Behoben
- **MS-SQL-Server-Reflektion crasht nicht mehr.** Der MSSQL-Dialekt exponiert
  `get_unique_constraints`/`get_indexes` teils als bare `NotImplementedError`
  (kein `SQLAlchemyError`), das am `except SQLAlchemyError` des Loaders vorbeilief
  und den ganzen `load()` abbrach — keine MSSQL-Datenbank war reflektierbar. Diese
  Aufrufe fangen jetzt `(SQLAlchemyError, NotImplementedError)`, konsistent zum schon
  vorhandenen `get_check_constraints`-Handling, und fallen sauber auf leer zurück.
  Gegen ein Live-SQL-Server-2022 verifiziert (beide MSSQL-Integrationstests grün,
  inkl. AP-63·S3-Routine-Reflektion); CI-Regressionstest via
  `NotImplementedError`-werfendem Fake-Inspector.

## [0.55.0] — 2026-06-29

### Hinzugefügt
- **Stored Procedures, Functions, Oracle Packages und Oracle Synonyme als vier neue read-only
  Sidebar-Kategorien (AP-63·S3):** reflektiert via Pro-Dialekt-Katalog-SQL (`pg_proc` für
  PostgreSQL; `all_objects`/`all_source` für Oracle; `sys.objects`/`sys.sql_modules` für MSSQL;
  Synonyme via `all_synonyms`, nur Oracle). Jede Kategorie wird nur bei N>0 angezeigt; das Detail
  enthält den Quelltext/die Definition. Das Model bekommt `Routine(name, kind, sql)` (kind ∈
  procedure/function/package) + `Synonym(name, target)` sowie zwei neue `Schema`-Felder
  `routines`/`synonyms`; `/api/schema` serialisiert `procedures`, `functions`, `packages`,
  `synonyms` (je `{"name","sql"}`, Synonyme `{"name","target"}`). Display-only — kein Daten-Tab,
  keine Join-Teilnahme. Skip-guarded Live-Integrationstests für PostgreSQL, Oracle und MSSQL;
  SQLite/andere liefern nichts.

## [0.54.0] — 2026-06-29

### Hinzugefügt
- **Sequences und Materialized Views als zwei neue read-only Sidebar-Kategorien (AP-63·S2b):**
  reflektiert via SQLAlchemy (`get_sequence_names` / `get_materialized_view_names`). Sequenzen
  zeigen ihren Namen; Materialized Views zeigen Spalten + Definition (display-only, kein Daten-Tab).
  Das Model bekommt `Sequence` + `Schema.sequences`/`materialized_views` (Matviews reusen das
  `View`-Shape); `/api/schema` serialisiert beide; die Sidebar zeigt jede Kategorie nur wenn
  vorhanden. Echte Reflektion funktioniert auf **PostgreSQL/Oracle** (skip-guarded Live-Test
  `tests/test_pg_integration.py`, `LUCENT_PG_TEST_URL`); SQLite/MSSQL liefern nichts.

## [0.53.0] — 2026-06-29

### Hinzugefügt
- **Trigger als neue read-only Sidebar-Kategorie (AP-63·S2):** Trigger werden jetzt reflektiert
  (Name, besitzende Tabelle, Quelltext) und als eigene „Trigger"-Sidebar-Kategorie angezeigt
  (nur wenn vorhanden). Die Reflektion nutzt dialekt-Katalog-SQL — **SQLite** via `sqlite_master`;
  andere Dialekte liefern vorerst nichts (PG/Oracle-Trigger sind ein Fast-Follow). Das
  Trigger-Detail ist schlank: Definition (besitzende Tabelle) + der `CREATE TRIGGER`-Quelltext
  im SQL-Tab, kein Daten-Tab. Das Model bekommt `Trigger` + `Schema.triggers`; `/api/schema`
  serialisiert sie; die Demo-CMDB erhielt einen Trigger. Sequences und Materialized Views
  bleiben AP-63·S2b. Nur Anzeige — Trigger werden nie ausgeführt und nehmen nicht an Join-Pfaden teil.

## [0.52.0] — 2026-06-29

### Hinzugefügt
- **Indizes + Check-Constraints im Tabellen-Detail (AP-63·S1):** Der „Definition"-Tab des
  Tabellen-Details listet jetzt **alle Indizes** (Name, Spalten, `unique`-Badge) und
  **Check-Constraints** (Name, Ausdruck), read-only via SQLAlchemy-Reflection
  (`get_indexes()` / `get_check_constraints()`, alle Engines inkl. SQLite). Das Model bekommt
  `Index`/`CheckConstraint` und `Table.indexes`/`check_constraints`; `/api/schema` serialisiert
  sie. Die Demo-CMDB erhielt einen Index (`ix_host_cluster`) und einen Check
  (`VMDisk.SizeGB > 0`). Nur Anzeige — das rekonstruierte DDL und die Join-Pfade bleiben
  unverändert; Expression-/Funktions-Indizes werden übersprungen.

## [0.51.0] — 2026-06-29

### Hinzugefügt
- **Subset-IN-Listen (AP-56c):** Das Panel „Entität exportieren" kann jetzt die referenzielle
  **Export-Identität** exportieren — je Closure-Tabelle die PK-Menge als self-contained read-only
  `SELECT * FROM tab WHERE pk IN (…);`. Composite-PKs nutzen die portable `(a = … AND b = …) OR …`-Form
  (kein Row-Value-IN); Literale werden typgerecht gerendert (Strings `'…'` mit verdoppeltem `'`).
  Die Schlüssel werden aus dem AP-56b·Stufe-2-Dump abgeleitet (`core/subset.py::subset_keys`/`subset_in_list_sql`)
  über den neuen Endpoint `POST /api/subset/inlists`; die UI bekommt einen Button „IN-Listen (SQL)",
  der eine `.sql` herunterlädt (ein annotierter Block je Tabelle). Tabellen ohne PK werden laut
  markiert (`incomplete`). Hinweis: PK-Literale nehmen int/str/Decimal/bool an; datetime/bytes-PKs
  rendern best-effort.

## [0.50.0] — 2026-06-29

### Hinzugefügt
- **Subset-Daten-Dump (AP-56b·Stufe 2):** Das Panel „Entität exportieren" kann jetzt die
  echten Zeilen der referenziellen Hülle exportieren. Ein neues `core.datapreview.dump_subset_rows`
  führt die AP-56a-Hüll-SELECTs read-only aus und erfasst die Zeilen je Closure-Tabelle;
  ein Per-Tabelle-Cap (`config.MAX_RESULT_ROWS`) wird mit lautem Truncation-Flag durchgesetzt
  (erkannt über `cap + 1`-Fetch), und eine gescheiterte Tabelle wird als Fehler gemeldet,
  während die übrigen weiter dumpen. Neuer Endpoint `POST /api/subset/dump` liefert ein
  JSON-Bundle `{start, truncated, incomplete, row_cap, tables[{columns, rows, row_count,
  truncated, error}]}`; die UI bekommt einen Button „Daten-Dump (JSON)", der das Bundle
  client-seitig herunterlädt (Browser-nativer Blob, keine Server-Datei). Read-only — kein
  Schreiben. Explizite IN-Listen bleiben ein Folge-AP.

## [0.49.0] — 2026-06-29

### Hinzugefügt
- **Subset-Live-Zeilenzahlen (AP-56b·Stufe 1):** Das Panel „Entität exportieren" kann die
  AP-56a-Hüll-SELECTs jetzt read-only ausführen und je Closure-Tabelle die echte Zeilenzahl
  plus eine Summe anzeigen. Ein neuer `count_sql`-Wrapper (`SELECT COUNT(*) FROM (<Hüll-SELECT>)`,
  Oracle-portabler Alias) speist `core.datapreview.count_subset_rows`, das jede Tabelle
  resilient zählt (scheitert eine, wird sie als Fehler gemeldet, die übrigen zählen weiter).
  Neuer Endpoint `POST /api/subset/run` liefert `{tables[], total, incomplete}`; die UI
  bekommt einen Button „Zeilen zählen (live)", eine Spalte „Zeilen" und eine „Summe"-Fußzeile.
  Nur Zählung — kein Daten-Dump, kein Schreiben. IN-Listen/Daten-Dump = AP-56b·Stufe 2.

## [0.48.3] — 2026-06-29

### Behoben
- Die SQL-Ausgabebox im SQL-Builder behält jetzt auch vor dem ersten „Generieren" eine
  volle Höhe (vorher ein schmaler Streifen, der das Copy-Icon halb abschnitt) und zeigt
  im Leerzustand einen Platzhalter-Hinweis.

## [0.48.2] — 2026-06-28

### Behoben
- HAVING-Vergleichswerte werden jetzt typgerecht gebunden: ein numerisch aussehender
  Wert (z. B. `HAVING COUNT(...) > 1`) wird als Zahl statt als String gebunden. Vorher
  lieferte die read-only Vorschau in SQLite still 0 Zeilen (ein Aggregat-Ausdruck hat
  keine Spalten-Affinität, ein TEXT-gebundenes `'1'` ist nie gleich dem Integer-COUNT).
  Das generierte SQL war schon korrekt; nun stimmt auch die Vorschau.

### Doku
- Alle sieben Oberflächen-Screenshots auf die aktuelle UI erneuert (1920×1080) und auf
  volle Content-Breite gestellt; zwei neue Screenshots zeigen die SQL-Builder-Klausel-
  Sektionen (Filter / Sortierung / Spalten sowie Aggregat mit GROUP BY + HAVING).

## [0.48.1] — 2026-06-28

### Geändert
- Verbindungsformular überarbeitet (AP-64): das Feld „Name zum Speichern" fluchtet
  jetzt mit den Feldern darüber; der alte „Verbinden"-Button entfällt; ein neuer
  „Testen"-Button (links von „Speichern", unter den Feldern) prüft die Verbindung
  read-only und zeigt das Ergebnis in einem Infofeld unter den Buttons. Das Laden
  eines Schemas bleibt eine Topbar-Aktion auf einer gespeicherten Verbindung.
  Nutzt `/api/connect`.

### Behoben
- Verbindungsfehler (z. B. unerreichbarer Oracle-Host) werden jetzt als HTTP 400
  mit der echten Fehlermeldung gemeldet statt als 500 — der neue „Testen"-Button
  zeigt damit die wahre Ursache.

## [0.48.0] — 2026-06-28

### Hinzugefügt
- Database-Subsetting — Schema-Footprint + Export-Skelett (AP-56a): aus Start-Tabelle
  + Wurzel-Filter wird die referenzielle FK-Hülle berechnet (abhängige Kinder abwärts,
  Lookup-Eltern aufwärts; „down-then-up" ohne Re-Descent, zyklus-sicher, tiefenbegrenzt)
  und je einbezogener Tabelle ein read-only SELECT erzeugt, das zur Wurzel zurück-joint.
  Neuer Modus „Entität exportieren" + read-only Endpoint `/api/subset`. Führt nichts aus;
  der Live-Walk mit echten Zeilenzahlen ist das zurückgestellte AP-56b.

## [0.47.0] — 2026-06-28

### Hinzugefügt
- Geschärfte Implied-FK-Erkennung (AP-55): neben dem exakten PK-Namen-Match wird
  jetzt auch eine Spalte mit ID-Suffix erkannt, deren Stamm (Groß/Klein-, Trenner-
  und Plural-normalisiert) eine andere Tabelle benennt, sofern deren Single-Column-PK
  eine konventionelle ID-Form ist (`id`/`uuid`/`guid`/`<Stamm>id`). Jeder Treffer trägt
  eine Confidence-Stufe (hoch/mittel/niedrig) und erscheint im Info-Panel, klar als
  geraten markiert (kein FK wird angelegt, keine SQL-Änderung). Cross-Schema-Matching
  bleibt zurückgestellt (braucht Multi-Schema-Reflection, Gate wie AP-57).

## [0.46.0] — 2026-06-28

### Hinzugefügt
- Cross-Schema-FK-Diagnose (read-only): FKs, die auf ein anderes Schema zeigen,
  werden jetzt reflektiert (`referred_schema`) und im Info/Übersicht-Panel als
  „Cross-Schema-FKs"-Count plus Kantenliste (`Tabelle.Spalte → Schema.Tabelle.Spalte`)
  angezeigt. Beantwortet empirisch, ob eine DB Cross-Schema-FKs nutzt — das
  Entscheidungs-Gate für die volle Cross-Schema-Join-Stufe. Keine SQL-Änderung. (AP-54)
  Bekannte Einschränkung: zählt Kanten anhand des reflektierten `referred_schema`;
  ohne explizit gewähltes Schema können Dialekte, die Same-Schema-FKs mit dem
  Default-Schemanamen qualifizieren, über-melden.

## [0.45.3] — 2026-06-28

### Behoben
- Verbindungsformular: die Feldzeilen fluchten jetzt sauber. Die Label-Spalte hat
  eine feste Breite (lange Labels wie „Server-Zertifikat vertrauen" brechen
  innerhalb der Spalte um, statt ihr Feld nach rechts zu schieben) und alle
  Inputs/Selects teilen eine Breite — so liegen alle Felder über
  SQLite/PostgreSQL/MySQL/MSSQL/Oracle an einer Linie. Nur CSS. (AP-60)

## [0.45.2] — 2026-06-28

### Geändert
- SQL-Builder-Layout: jede Klausel-Sektion (Filter, Sortierung, Spalten, HAVING)
  ist jetzt ein einzelner „+ Label"-Button in der linken Spalte mit der ersten
  Zeile auf derselben Linie — statt einer eigenen „Label [+]"-Kopfzeile. Der
  ganze Builder ist ein 2-Spalten-Raster; alle Feld-Spalten fluchten mit
  Start/Ziel. Spart eine Zeile je gefüllter Sektion. Nur Markup/CSS — IDs und
  erzeugte SQL unverändert. (AP-59)

## [0.45.1] — 2026-06-28

### Behoben
- SQL-Builder: die HAVING-Zeilen rendern jetzt wie die übrigen Klausel-Sektionen
  (Filter/Sortierung/Spalten) — gleiches Flex-Layout, gleiche Einrückung und ein
  kleiner quadratischer Löschbutton statt eines aufgeblähten 140px-Kastens.
  HAVING (v0.42.0) entstand vor dem AP-B-Layout und hatte kein passendes CSS.
  Nur CSS — keine Verhaltensänderung. (AP-58)

## [0.45.0] — 2026-06-28

### Hinzugefügt
- SQL-Analyzer: neue Kategorie „Optimierungs-Vorschläge" (getrennt von den
  Warnungen) mit vier schema-freien AST-Heuristiken: überflüssiges DISTINCT
  neben GROUP BY, ORDER BY ohne LIMIT, OR im Top-Level-WHERE (kann
  Indexnutzung verhindern) und eine Nicht-EXISTS-Unterabfrage in WHERE (oft
  besser als JOIN/EXISTS). Read-only, nur Hinweise — kein Umschreiben. (AP-F)

## [0.44.0] — 2026-06-28

### Hinzugefügt
- SQL-Builder: jede Sortier-Zeile (ORDER BY) und jede Spalten-Zeile trägt jetzt
  kleine ↑/↓-Buttons (kein Drag & Drop), um Zeilen innerhalb ihrer Sektion zu
  verschieben. Da das Formular in DOM-Reihenfolge gelesen wird, ändert das
  Verschieben die erzeugte SQL: ORDER BY = Sortier-Priorität, Spalten =
  SELECT-/GROUP-BY-Reihenfolge. Das ↑ der ersten und das ↓ der letzten Zeile
  sind deaktiviert. Verschieben bleibt gestaged (kein Auto-Rebuild) — mit
  „Generieren" anwenden. WHERE/HAVING bewusst ohne Move (Reihenfolge dort
  kosmetisch). Nur Markup/CSS + JS — keine Route, kein `core/`. (AP-E)

### Behoben
- Schema-Graph-Legende: der `1-N`-Chip fluchtet jetzt linksbündig mit dem
  `N-1`-Chip (überflüssiges `margin-left` entfernt, das ihn leicht nach rechts
  schob). Nur CSS.

## [0.43.4] — 2026-06-28

### Geändert
- SQL-Builder: die Join-Typ-Dropdowns sitzen jetzt inline in der aktiven
  Kandidatenpfad-Zeile (neben den 1-N/N-1-Richtungs-Chips), die separate
  Join-Typ-Zeile entfällt. Die Fan-out-Erklärung wanderte aus der Builder-
  Hinweiskachel in die Schema-Graph-Legende (1-N vervielfacht Zeilen / N-1
  sicher). Nur Markup/CSS — keine Verhaltensänderung.

## [0.43.3] — 2026-06-28

### Geändert
- SQL-Builder-Layout: die Klausel-Builder sind jetzt vier beschriftete
  Sektionen (Filter, Sortierung, Spalten, HAVING) mit je eigenem kompaktem
  „+"-Button; die Ausgabe-Optionen (DISTINCT, LIMIT, Dialekt) und der
  „Generieren"-Button liegen in einer getrennten Aktionsleiste unten. Nur
  Markup/CSS — keine Verhaltensänderung, alle Element-IDs und das generierte
  SQL bleiben gleich.

## [0.43.2] — 2026-06-28

### Geändert
- Builder von „Join-Builder" in „SQL-Builder" umbenannt — UI (Menü, Tab,
  Bau-Button heißt jetzt „Generieren") und aktuelle Doku. Interne Bezeichner
  im Gleichschritt umbenannt (`jb-`→`sb-`, `jb_`→`sb_`, `JB_`→`SB_`,
  `joinbuilder`→`sqlbuilder`). Keine Verhaltensänderung; der Endpoint
  `/api/joinpath` bleibt unverändert.

## [0.43.1] — 2026-06-28

### Behoben
- GROUP BY wird jetzt auch aus Aggregaten in HAVING und ORDER BY abgeleitet,
  nicht nur aus der SELECT-Liste. Bisher erzeugte eine nicht-aggregierte
  SELECT-Spalte zusammen mit einem Aggregat, das allein in HAVING oder ORDER BY
  stand, GROUP-BY-loses SQL, das strikte DBs (z. B. PostgreSQL) ablehnen.
  Rückwärtskompatibel: kein Aggregat → weiterhin kein GROUP BY; alle
  SELECT-Spalten aggregiert → weiterhin keins. Änderung in `core/sqlgen.py`.

## [0.43.0] — 2026-06-28

### Hinzugefügt
- COUNT(*) + COUNT(DISTINCT): zwei neue Aggregat-Optionen. COUNT(*) zählt
  Zeilen pro Gruppe (Spalte wird ignoriert; die zugehörige Tabelle wird dennoch
  in den Join eingebunden, d. h. „COUNT(*) auf Tabelle T + GROUP BY K" zählt
  die eingebundenen T-Zeilen je Gruppe). COUNT(DISTINCT Spalte) zählt
  eindeutige Werte. Beide Optionen funktionieren in SELECT, HAVING und ORDER BY.
  Kein neues Core-Modul, kein neuer Endpoint (Änderungen in `core/sqlgen.py`
  und `web/static/js/app.js`). Noch offen: Cross-Schema-Joins.

## [0.42.0] — 2026-06-28

### Hinzugefügt
- Aggregat-Operationen — HAVING + ORDER BY auf Aggregaten: ORDER BY kann nun
  nach einem Aggregat sortieren (z. B. `ORDER BY COUNT(...) DESC`); eine neue
  HAVING-Klausel filtert Gruppen nach einem Aggregat (skalarer Vergleich
  `= != < > <= >=`, parametrisierter Wert). Klauselreihenfolge:
  WHERE → GROUP BY → HAVING → ORDER BY → LIMIT. Die read-only-Ausführung
  wertet HAVING aus. Aggregat ist auf einer HAVING-Zeile Pflicht. Kein neues
  Core-Modul, kein neuer Endpoint (Änderungen in `core/sqlgen.py`,
  `web/routes.py`, `web/static/js/app.js`).
  Noch offen: COUNT(*)/COUNT(DISTINCT), Cross-Schema-Joins.

## [0.41.0] — 2026-06-28

### Hinzugefügt
- Tier-3 GROUP BY / Aggregatfunktionen: jede SELECT-Spalte kann eine
  Aggregatfunktion (COUNT/SUM/AVG/MIN/MAX) tragen; GROUP BY wird automatisch
  aus den nicht-aggregierten Spalten abgeleitet. Generiertes SQL erhält eine
  GROUP BY-Klausel; die read-only-Ausführung führt gruppierte Abfragen aus.
  Änderungen in `core/sqlgen.py`, `web/routes.py` und `web/static/js/app.js`;
  kein neues Core-Modul, kein neuer Endpoint.
  Noch offen: HAVING, COUNT(*)/COUNT(DISTINCT), Cross-Schema-Joins.

## [0.40.0] — 2026-06-28

### Hinzugefügt
- Tier-2 Tabellen-/Spaltenkommentare: Kommentare werden bei der Reflection
  gelesen und im UI (Detailliste + UML-Karten) als Hover-Tooltip angezeigt;
  generiertes SQL unverändert.

## [0.39.0] — 2026-06-28

### Hinzugefügt
- Oracle-Verbindungen: Verbinden/Reflektieren via python-oracledb (Thin-Mode,
  kein Instant Client), Adressierung per Service-Name; System-Schemas im
  Schema-Wähler gefiltert.

## [0.38.0] — 2026-06-28

### Hinzugefügt
- Multi-Schema: ein Schema-Wähler reflektiert/abfragt jedes einzelne Schema;
  erzeugte SQL ist schema-qualifiziert (`schema.table`). Neues `/api/schemas`.

## [0.37.0] — 2026-06-27

### Hinzugefügt
- 1-1-Erkennung berücksichtigt jetzt auch Unique-Indizes (voll-spaltig,
  nicht-partiell) — nicht nur UNIQUE-Constraints/PK. Partielle und
  Expression-Indizes bleiben bewusst ausgeschlossen.

## [0.36.0] — 2026-06-27

### Hinzugefügt
- 1-1-Erkennung: absteigende FK mit eindeutiger Kind-Spalte (UNIQUE/PK) gilt
  als 1-1 statt 1-N — keine falsche Fan-out-Warnung mehr.

## [0.35.0] — 2026-06-27
### Hinzugefügt
- waitress als WSGI-Server im Normalbetrieb (Debug behält Dev-Server mit Auto-Reload).

## [0.34.1] — 2026-06-27
### Hinzugefügt
- **AP-34 — Info-Dialog:** Das Tray-„Info" öffnet jetzt einen echten Dialog (eigener Prozess,
  `launcher/about.py`) mit **Ersteller, Art (read-only), Repo, URL/Port und vollem Stack**
  (Python/Flask/SQLAlchemy/NetworkX/sqlglot/Cytoscape/pystray/Pillow) sowie den Pro-Nutzer-Pfaden.
  Inhaltsbasierte Fenstergröße (keine Zeilenumbrüche), **Zentrierung auf dem primären Monitor**
  (Multi-Monitor-fest via xrandr auf Linux).
- **AP-34 — Linux-Tray-Menü:** mit dem AppIndicator/GTK-Backend (PyGObject) funktioniert das
  Kontextmenü (Öffnen/Info/Beenden) auch auf Linux. Optionale Deps in `requirements-tray-linux.txt`
  (Setup-Schritte auf der Betriebsseite); ohne sie Xorg-Fallback (Icon ohne Menü). Windows: nativ.
### Behoben
- **AP-34 — sauberes Beenden:** der Launcher räumt den `app.py`-Kindprozess bei **jedem** Ende
  (Menü „Beenden", Schließen, SIGTERM/SIGINT, normales Exit) ab → **keine verwaisten Prozesse**,
  Port wird frei. 232 Tests grün.

## [0.34.0] — 2026-06-27
### Hinzugefügt
- **AP-34 (Kern) — Tray-Icon-Launcher:** Ein-Klick-Start, ohne dass der Nutzer ein venv
  einrichtet. Eine Verknüpfung auf `run.ps1 -Action tray` (Linux: `run.sh --tray`) baut beim
  ersten Start das venv automatisch (bestehende adaptive Logik) und startet einen **fensterlosen**
  Python-Tray-Launcher (`launcher/`): Tray-Menü **Im Browser öffnen · Info · Beenden**,
  Auto-Browser beim Start (pollt bis der Server antwortet), „Beenden" stoppt den App-Prozess →
  Port frei. Neue Pakete `pystray`/`Pillow` (als Wheels gebündelt, NO-CDN). `launcher/core.py`
  ist stdlib-only und vollständig getestet; Tray-GUI auf Windows/Desktop zu verifizieren.
  *Offen:* Live-Log-Fenster, automatisches Ausrollen der Verknüpfung.

## [0.33.0] — 2026-06-27
### Hinzugefügt
- **AP-31 (Kern) — Multi-User-Basis:** Mehrere Nutzer können die App kollisionsfrei auf einer
  Maschine betreiben.
  - **Dynamische Port-Wahl pro Session:** ohne `LUCENT_PORT` erst 5057 (Hub-reserviert), sonst
    automatisch ein freier Port; `LUCENT_PORT=<n>` erzwingt fest, `=0` immer dynamisch. Die
    tatsächliche URL wird beim Start ausgegeben. Bind weiterhin nur `127.0.0.1`.
  - **Pro-Nutzer-Datenpfade:** `config.json` + Logs liegen im OS-Nutzerverzeichnis (Slug `luDBxP`;
    Linux `~/.config` bzw. `~/.local/state`, Windows `%LOCALAPPDATA%`). Overrides `LUCENT_CONFIG_DIR`/
    `LUCENT_LOG_DIR`. Eine vorhandene App-Verzeichnis-`config.json` wird einmalig übernommen.
  - Neues pures Stdlib-Modul `core/userpaths.py` (Pfade + `pick_port`/`resolve_port` + Migration).
  - `run.sh`/`run.ps1` brechen bei belegtem Port **nicht mehr ab** — `app.py` wählt selbst einen
    freien Port. 220 Tests grün (1 skipped).
  - *Offen (Rest von AP-31):* lokaler WSGI-Server (waitress), Idle-Shutdown/Stop, Deployment-Packaging.

## [0.32.1] — 2026-06-27
### Geändert
- **AP-45 Feinschliff — Filter sofort wirksam:** Wird ein Filterwert gesetzt (getippt oder aus dem
  DISTINCT-Dropdown gewählt), ein wertloser Operator (`IS NULL`/`IS NOT NULL`) gewählt oder eine
  Filterzeile entfernt, baut der Join-Builder **sofort neu** — die `WHERE`-Bedingung erscheint
  umgehend im SQL und im Ergebnis (vorher erst nach „Aktualisieren").
### Behoben
- **DISTINCT-Dropdown zeigte gelegentlich die falsche Spalte:** Beim Vorbelegen einer Filterzeile
  (z. B. via „Als Filter") wurde kurzzeitig auch die Default-Spalte geladen; bei ungünstigem
  Timing füllte deren Antwort die Vorschlagsliste. `_loadFilterDistinct` verwirft jetzt veraltete
  Antworten (Race-Guard) — es gewinnt immer die aktuell gewählte Spalte.
### Doku
- Referenz **Oberfläche/Architektur**: die **zwei „DISTINCT"** klar abgegrenzt — die `DISTINCT`-Checkbox
  fließt als `SELECT DISTINCT` ins generierte SQL, das **Filter-Wertdropdown** (`/api/distinct`) ist
  dagegen ein **separater Lookup** auf eine Spalte und erscheint **nicht** im Join-SQL.

## [0.32.0] — 2026-06-27
### Hinzugefügt
- **AP-45 — Ergebnis-Hilfen Teil 2: Spaltenkopf-Aktionen + DISTINCT-Filterwerte:**
  - **Klickbare Spaltenköpfe** in der Ergebnistabelle: ein Klick auf eine Spalte öffnet ein
    Menü mit **Sortieren ASC/DESC**, **Als Filter…** und **Spalte entfernen**. Sortieren legt
    eine ORDER-BY-Zeile an und baut neu; „Als Filter" füllt eine Filterzeile vor und fokussiert
    das Wertfeld; „Spalte entfernen" wirkt auf Zusatzspalten — **Start-/Ziel-Spalten** definieren
    den Join-Pfad und sind geschützt (Menüeintrag deaktiviert).
  - **Filter-Wertfeld mit echten Werten:** jedes Wertfeld ist mit einer `<datalist>` der echten
    **DISTINCT-Werte** der Spalte hinterlegt (Auswahl per Dropdown, Freitext bleibt möglich).
    Neues read-only Endpoint **`/api/distinct`** (`SELECT DISTINCT … ORDER BY …`, auf
    `config.DISTINCT_LIMIT` begrenzt, spalten-validiert, best-effort wie `/api/orphan_check`).
  - **`/api/joinpath/run`** liefert zusätzlich **`columns_meta`** (Tabelle/Spalte je Ausgabespalte
    in Selektionsreihenfolge) → jeder Spaltenkopf lässt sich eindeutig seiner Quellspalte zuordnen,
    auch wenn zwei verbundene Tabellen denselben Spaltennamen haben. 205 Tests grün, 1 skipped.

## [0.31.0] — 2026-06-27
### Behoben
- **Parsefehler zeigte ANSI-Müll:** sqlglot unterstreicht das Fehler-Token mit ANSI-Farbcodes,
  die im Browser als `□[4m…□[0m` erschienen. Werden jetzt **entfernt** — die Meldung ist sauberer
  Text. Layout neu: Label „Konnte nicht geparst werden:", darunter die Meldung (beginnend mit
  „Invalid expression …") samt mehrzeiligem SQL-Ausschnitt in einem roten Block (das „abgesetzte"
  Stück war dieser Kontext-Ausschnitt).
### Geändert
- **AP-49 — Analyzer-Feinschliff:** Eingabe-Textbox per Default **größer** (~17 rem); der
  **read-only**-Hinweis sitzt jetzt als grünes **Badge** abgesetzt neben „Analysieren". 200 Tests grün, 1 skipped.

## [0.30.0] — 2026-06-27
### Geändert
- **AP-48 — SQL-Analyzer: größere Eingabe + Tippfehler-Lint:**
  - Die Eingabe-Textbox ist **größer** (volle Breite, ~14 Zeilen) und nur **vertikal**
    in der Höhe verstellbar (nicht in der Breite, `resize: vertical`).
  - Neuer Lint **`SUSPICIOUS_ALIAS`**: Ein vertippter Join-Typ wie `LEFTI` ist für sqlglot
    syntaktisch gültig (Tabellen-**Alias**) und damit kein Parser-Fehler. Die Heuristik
    erkennt jetzt Aliasse, die einem Join-Schlüsselwort (LEFT/RIGHT/INNER/OUTER/FULL/CROSS)
    stark ähneln, und warnt vor dem möglichen Tippfehler. *Hinweis:* sqlglot bleibt ein
    toleranter Parser — echte Syntaxfehler (z. B. ein fehlendes `"`) werden erkannt, aber
    nicht jeder Tippfehler ist ein Syntaxfehler. 199 Tests grün, 1 skipped.

## [0.29.1] — 2026-06-27
### Behoben
- **Waisen-Chip war falsch-positiv:** Die Probe testete jeden Join **isoliert** und meldete
  Waisen, die im Pfad-Kontext gar nicht erscheinen (unerreichbar von der FROM-Tabelle, oder
  von nachfolgenden INNER-Joins wieder herausgefiltert) — der Chip versprach eine Änderung,
  die das Umschalten auf LEFT dann nicht brachte. `/api/orphan_check` **zählt jetzt das echte
  Ergebnis** (COUNT je Join-Typ vs. INNER, übrige Schritte auf aktuellem Stand) und meldet nur
  Typen, die die Zeilenzahl **tatsächlich** ändern. Chip und Tabelle sind damit konsistent.

## [0.29.0] — 2026-06-27
### Hinzugefügt
- **AP-47 — Pfad-Auswahl sichtbar + Waisen-Hinweis am Join-Typ:**
  - Die Pfad-Liste nutzt **`[*]` (aktiv) / `[ ]`** statt Bullets — der gewählte Alternativpfad
    ist eindeutig markiert (aktiver Pfad zusätzlich hervorgehoben).
  - Pro Join-Schritt zeigt ein **datengetriebener Waisen-Chip** (z. B. `⚠ LEFT/FULL`), welche
    Join-Typen hier **tatsächlich** unverknüpfte (Waisen-)Zeilen aufdecken. Neuer read-only
    Endpoint `/api/orphan_check` prüft per `NOT EXISTS`-Probe je Schritt links/rechts; die
    betroffenen Dropdown-Optionen werden zusätzlich amber getönt (so weit der Browser native
    `<option>`-Farben rendert). 197 Tests grün, 1 skipped.

## [0.28.1] — 2026-06-27
### Behoben
- **Graph bleibt beim Aufklappen der Detailkarten zentriert:** Erscheint unten der
  Detailbereich (Start/Ziel-Karten), rückt der Graph nach oben und wird in seinem
  kleineren Bereich **zentriert** — bei **gleichem Zoom** (`CY.center()` statt zu fitten),
  ohne Überlauf in den Kartenbereich. Beim Ausblenden zentriert er sich wieder im vollen Panel.

## [0.28.0] — 2026-06-27
### Geändert
- **AP-46 — Detailkarten folgen der Join-Builder-Auswahl:** Solange **nichts ausgewählt**
  ist, bleibt der Schema-Graph **zentriert** (der Detailbereich darunter ist ausgeblendet).
  Sobald Start/Ziel gesetzt sind — **auch wenn über die Dropdowns statt per Graph-Klick** —
  rückt der Graph nach oben und darunter erscheinen die **Tabellen-Detailkarten** für Start
  und Ziel (mit markierten Spalten), wie sonst beim Doppelklick auf einen Knoten. „Auswahl
  zurücksetzen" blendet den Bereich wieder aus. 195 Tests grün, 1 skipped.

## [0.27.0] — 2026-06-27
### Geändert
- **AP-44 — Join-Builder kompakter + Ergebnis-Hilfen:** Der obere Bereich ist gestrafft —
  die beiden Button-Zeilen (`Filter+/Sortierung+/Spalten+` und `DISTINCT/LIMIT/Dialekt/Bauen`)
  sind **eine** Zeile, die 1-N-Info sitzt als **kleine Kachel oben rechts** (keine eigene Zeile),
  engere Abstände + kompakteres SQL-Feld → **mehr Platz für die Ergebnistabelle**.
- **Ergebnis-Hilfen:** **NULL-Zellen** (Outer-Join-/Waisen-Zeilen) werden hervorgehoben;
  die Statuszeile zeigt jetzt **Zeilen · Join-Typ · Fan-out** (z. B. „8 Zeilen · LEFT · ⚠ 1-N").
  195 Tests grün, 1 skipped.

## [0.26.0] — 2026-06-27
### Geändert
- **AP-43 — Lesbares SQL-Layout:** Das generierte SQL ist jetzt **mehrzeilig formatiert** —
  eine Spalte pro Zeile, jeder `JOIN` auf eigener Zeile mit `ON`/`AND` darunter und
  **ausgerichteten `=`** bei zusammengesetzten Schlüsseln. Dadurch bleiben die Zeilen kurz
  (kein Horizontal-Scroll/keine Umbruch-Sorgen) und ein eingefügtes Statement ist sauber.
  Die **Copy/Anzeige**-Variante endet mit `;` (paste-and-run); das intern ausgeführte
  parametrisierte SQL ohne. 195 Tests grün, 1 skipped.

## [0.25.0] — 2026-06-27
### Geändert
- **AP-42 — Join-Builder-Politur:** Der verbose Fan-out-Warntext pro Ast („Ast „X" ist
  1-N (absteigend) — kann Zeilen vervielfachen") ist **raus** — die Richtung steht ohnehin
  als **N-1/1-N-Chip** an jedem Join. Stattdessen **eine** kompakte Kachel unter der
  Pfadliste: „**1-N** kann Zeilen vervielfachen (Fan-out)", nur wenn ein Pfad einen
  1-N-Schritt hat. Spart deutlich Platz.
- **SQL-Fenster bricht jetzt um** statt waagerecht zu scrollen (`white-space: pre-wrap`).
  Der Umbruch ist rein **visuell** — Copy/Paste liefert das Statement mit den echten
  Zeilenumbrüchen, bleibt also lauffähig.

## [0.24.2] — 2026-06-27
### Geändert
- **Ziel-Knoten jetzt Amber/Gold** statt Rot: Das Rot war auf der orangenen Pfad-Füllung
  noch zu ähnlich. Ziel = **Amber (#f3b305) mit dunkler Schrift**, hebt sich klar von Start
  (grün) und Pfad (orange) ab. Legende angepasst (so unterscheidet sich „Ziel" nun auch klar
  von „Analyzer: geschrieben"/rot).

## [0.24.1] — 2026-06-27
### Behoben
- **Ziel im Graph schlecht lesbar:** Der rote Ziel-**Ring** verschwamm mit der orangenen
  Pfad-Füllung. Endpunkte werden jetzt **voll eingefärbt** — Start grün, Ziel rot,
  Zwischenstationen orange — und heben sich klar ab. Legende auf gefüllte Quadrate angepasst.

## [0.24.0] — 2026-06-27
### Hinzugefügt
- **AP-41 — Join-Typ pro Schritt:** Im Join-Builder lässt sich jetzt **je Join-Station**
  der Typ wählen — **INNER** (Standard), **LEFT**, **RIGHT**, **FULL**. Pro Schritt ein
  Dropdown über der SQL-Ausgabe; eine Änderung baut SQL **und** Ergebnis neu. Damit gehen
  z. B. Start-Zeilen ohne Match nicht mehr verloren (LEFT statt INNER). `sqlgen`/`/api/joinpath`
  + `/api/joinpath/run` nehmen `join_types` (positionsweise; read-only-Ausführung bleibt
  parametrisiert). Der **SQL-Analyzer** erkannte Outer Joins bereits korrekt (LEFT/RIGHT/FULL/CROSS).
### Behoben
- **Graph-Marker passten nicht zur Legende:** Beim Bauen über die Dropdowns wurden Start/Ziel
  nicht eingefärbt (alle Knoten gleich). Jetzt markiert der Graph **Start grün / Ziel rot**
  (Ringe) auch ohne Klick-Auswahl — passend zur Legende. 194 Tests grün, 1 skipped.

## [0.23.0] — 2026-06-27
### Hinzugefügt
- **AP-40 — Graph-Legende** (klein, oben links im Schema-Graph): erklärt die
  Hervorhebungen — blau = Analyzer (gelesen/Joins), rot = Analyzer (geschrieben),
  orange = Join-Pfad, N-1/1-N = Join-Richtung, grüner/roter Rahmen = Start/Ziel.
### Behoben
- **Überlagernde Graph-Marker:** Join-Builder-Pfad und Analyzer-Markierungen sind jetzt
  **wechselseitig exklusiv** — die blaue Analyzer-Spur verschwindet, sobald ein Join-Pfad
  gebaut wird (und umgekehrt). Vorher blieben blaue Knoten/Kanten neben dem orangen Pfad
  stehen. Verifiziert via Playwright. 190 Tests grün, 1 skipped.

## [0.22.0] — 2026-06-27
### Hinzugefügt
- **AP-39 — SQL-Analyzer: Struktur-/Klauselanalyse, Graph-Zeichnung, Lints, Komplexität:**
  Der Analyzer wertet den sqlglot-AST jetzt deutlich tiefer aus (statt nur Typ + gelesene/
  geschriebene Tabellen). Neu im Panel: **Spalten**, **Joins** (Typ + ON-Bedingung),
  **Filter (WHERE)**, **GROUP BY/HAVING**, **Sortierung (ORDER BY)**, **DISTINCT/LIMIT**,
  ein **Struktur-Zähler** (Tabellen/Joins/Subqueries/CTEs/UNION/Window/Aggregate/CASE) und
  ein **Komplexitäts-Score** (gewichtet, Note A–E). Der **Schema-Graph zeichnet die JOIN-Kanten**
  des Statements (nicht mehr nur die Knoten einfärben). Zusätzliche statische Lints ohne DB:
  `SELECT_STAR`, `LEADING_WILDCARD` (LIKE '%…'), `FUNC_ON_COLUMN`. Weiterhin **read-only —
  nie ausgeführt**. `/api/analyze` liefert die neuen Felder. 190 Tests grün, 1 skipped.

## [0.21.0] — 2026-06-27
### Hinzugefügt
- **AP-38 — Kopierbares, lauffähiges SQL (Werte eingesetzt):** Die SQL-Anzeige und das
  Copy-Icon liefern jetzt **direkt ausführbares** SQL — Filterwerte werden als Literale
  eingesetzt (Zahlen roh, Strings in `'…'` mit `''`-Escaping, führende Nullen & LIKE bleiben
  String). Damit ist ein in einen externen SQL-Editor eingefügter SELECT sofort lauffähig,
  ohne `:p0`-Bind-Variablen ausfüllen zu müssen. Die **parametrisierte** Form (`:p0` + `params`)
  bleibt intern die read-only-**Ausführungs**­schiene (injection-sicher); `/api/joinpath`
  liefert beide als `sql` und `sql_inline`. 180 Tests grün, 1 skipped.

## [0.20.0] — 2026-06-27
### Hinzugefügt
- **AP-37 — Start ⇄ Ziel tauschen:** Neuer **⇄-Knopf** neben den Ziel-Dropdowns
  vertauscht Start- und Ziel-(Tabelle+Spalte), spiegelt die Graph-Marker und baut
  bei bereits gezeigtem Pfad sofort neu. Praktisch, weil die **warnungsfreie
  Richtung oft die umgekehrte** ist (aufsteigend zum Elternteil erzeugt kein Fan-out).
- **Doku:** Fan-out-Seite um **Beispiel 3** erweitert (langen Pfad lesen → Kette
  verkürzen *oder* Filter auf die „Viele"-Tabelle setzen; Faustregel + ⇄-Hinweis).

## [0.19.0] — 2026-06-27
### Hinzugefügt
- **AP-36 — Fan-out-Richtung pro Join sichtbar:** Jeder Join-Schritt eines Pfads
  trägt jetzt einen **Richtungs-Chip** — grün `N-1` (aufsteigend, sicher) oder
  gelb `1-N` (absteigend, kann Zeilen vervielfachen) — sowohl in der **Pfad-Liste**
  als auch als **Label an der hervorgehobenen Kante** im Schema-Graph. Macht
  sichtbar, dass ein Pfad eine *Mischung* aus N-1- und 1-N-Schritten ist, statt
  „alles 1-N". `/api/joinpath` liefert dafür pro Pfad ein neues `steps`-Feld
  (`left`/`right`/`to_many`); die bestehende `.path-warn`-Box bleibt. 172 Tests grün, 1 skipped.
- **Doku:** Neue Referenzseite **Fan-out-Warnung (1-N)** mit durchgerechneten
  Beispielen, inkl. Abschnitt „Warum beide Richtungen warnen — und eines trotzdem N-1 ist".

## [0.18.0] — 2026-06-27
### Hinzugefügt
- **AP-25 — Read-only SQL-Statement-Analyzer:** Neuer **SQL-Analyzer**-Tab; Statement
  wird via **sqlglot** (lokal gebündelt, kein CDN) geparst — **nie ausgeführt**.
  Zeigt Statement-Typ, gelesene/geschriebene Tabellen sowie Warnungen:
  `WRITE_STATEMENT`, `NO_WHERE` (UPDATE/DELETE ohne WHERE), `CARTESIAN_JOIN`;
  mit Verbindung zusätzlich `UNKNOWN_TABLE`/`UNKNOWN_COLUMN` (case-insensitiv).
  Beteiligte Tabellen werden im Graphen markiert (`analyze-read`/`analyze-write`).
  Funktioniert mit und ohne Verbindung. 165 Tests grün, 1 skipped.

## [0.17.0] — 2026-06-27
### Hinzugefügt
- **AP-30 — N-1-Stern (Auto-Weaving, Fan-out-Warnung):** Select-/ORDER-BY-/Filter-
  Tabellen werden automatisch in den Join-Baum gewebt — stilles Verwerfen entfällt.
  Unerreichbare Tabellen lösen einen `NoPathError` aus. Absteigende (1-N) Äste
  erzeugen eine **nicht-blockierende Fan-out-Warnung** pro Pfad (`warnings`-Feld
  in `/api/joinpath`); das Frontend zeigt diese als `.path-warn`-Box am betroffenen
  Pfad an. 144 Tests grün, 1 skipped.

## [0.16.0] — 2026-06-27
### Hinzugefügt
- **AP-12 (Abschluss) — MSSQL-Verschlüsselungsfelder in der UI:** Verbindungs-Tab
  hat für MS SQL Server zwei Tri-State-Dropdowns **Verschlüsselung** (`Encrypt`)
  und **Server-Zertifikat vertrauen** (`TrustServerCertificate`) — Standard/ja/nein;
  „Standard" lässt den Parameter weg. Persistiert mit gespeicherten Verbindungen.
- **AP-12 real verifiziert:** skip-guardeter Integrationstest gegen SQL Server 2022
  (`tests/test_mssql_integration.py`, `LUCENT_MSSQL_TEST_URL`) — provisioniert ein
  Schema mit FK und prüft die Reflection (ODBC Driver 18 / `msodbcsql18`).

## [0.15.0] — 2026-06-26
### Hinzugefügt
- **AP-29 — SQL-Dialekt umschalten:** Dialekt-Dropdown im Join-Builder
  (SQLite · PostgreSQL · MySQL · MSSQL · Oracle). Das read-only SELECT wird
  dialekt-treu gerendert — **Identifier-Quoting** (`"x"` / `` `x` `` / `[x]`)
  und **Zeilenlimit** (`LIMIT n` / `SELECT TOP n` / `FETCH FIRST n ROWS ONLY`).
  Default aus der Verbindung; **Anzeige** nutzt den gewählten Dialekt, die
  **Ausführung** den der echten Verbindung. Hand-gerollte `Dialect`-Schicht in
  `core/sqlgen.py` (keine neue Abhängigkeit), test-first, 137 Tests grün.
### Geändert
- **Identifier werden jetzt immer quotiert** (auch im SQLite-Default):
  `SELECT "VirtualMachine"."VMID"` statt `SELECT VirtualMachine.VMID`.

## [0.14.0] — 2026-06-26
### Geändert
- **AP-14 (Teil 2, Linux) — Python-3.14-AppImage:** venv und AppImage laufen jetzt
  gegen **Python 3.14.6** (user-lokal via `uv`, kein Root; alle 5 C-Extensions als
  **cp314-manylinux**-Wheels → venv rein aus Wheels, 125 Tests grün). AppImage
  gegen 3.14 gebaut & verifiziert (HTTP 200, bundelt 3.14.6).
- **AppImage-Fixes (`run.sh` AppRun):** **versions-bewusstes App-Update** (Code wird
  bei Versionswechsel erneuert, Nutzerdaten `config.json`/`Logs/` bleiben — vorher
  lief stiller Alt-Code weiter, real 0.1.0 statt der gebauten Version); **Browser**
  öffnet bevorzugt Chrome/Chromium statt `xdg-open`-Default.
### Behoben
- **`run.sh` unter Python 3.14:** `re.split(..., 1)` (positionsbasiertes `maxsplit`)
  löste einen DeprecationWarning aus → `maxsplit=1`.

## [0.13.0] — 2026-06-26
### Geändert
- **AP-33 — Logging sauber gemacht:** `core/log.py` rotiert jetzt (`RotatingFileHandler`,
  ~1 MB × 5) statt unbegrenzter `app.log`; Level via `LUCENT_LOG_LEVEL`
  (`LUCENT_DEBUG` ⇒ DEBUG), Logpfad via `LUCENT_LOG_DIR` (Pro-Nutzer-Hook;
  volle Terminal-Server-Verdrahtung bleibt AP-31). `init_logging` ist idempotent
  + reconfigurierbar (Handler-Ersatz) mit Startup-Zeile. Neu: **Request-Logging**
  (Methode · Pfad · Status · Dauer) in der `web/`-App-Factory — Layering gewahrt
  (`core/log.py` bleibt Flask-frei). 125 Tests grün (7 neue, test-first).

## [0.12.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 2, Linux) — `run.sh` abbruchsicher + idempotent (Parität zu
  `run.ps1`):** Der Linux-Launcher heilt sich nach abgebrochenen Läufen selbst.
  Jeder Schritt prüft seine Vorbedingungen und meldet seinen Status
  (`_ok`/`_warn`/`_info`/`_hdr`/`_fail`):
  - **venv-Integrität statt nur Existenz** (`venv_healthy`: `python -c import sys`);
    ein halbes/kaputtes venv wird automatisch neu gebaut.
  - **Echter Paket-Vollständigkeits-Check:** `pip check` **plus** Vorhandensein
    jeder in `requirements.txt` gelisteten Distribution (`importlib.metadata`) —
    fängt sowohl abgebrochene Installs als auch ein frisch gebautes, leeres venv.
  - **Atomarer Stamp:** `.req_stamp` wird erst **nach** erfolgreichem Install
    geschrieben; ein abgebrochener Install wiederholt sich beim nächsten Lauf.
  - **Port-/Instanz-Check** vor App-Start (5057 belegt via `ss`/`lsof` → klare
    Abbruch-Meldung statt Crash).
  - **Robustes Menü:** ein fehlgeschlagener Schritt beendet das Menü nicht mehr
    (Subshell-Isolierung, bash-Pendant zum try/catch).
  - **Exit-Codes nicht mehr verschluckt:** das `|| true` in `do_start`/
    `do_skip_setup` entfernt; der App-Exit-Code wird sauber durchgereicht.
  - **`--debug`-Flag** (Pendant zu `run.ps1 -DebugMode`, setzt `LUCENT_DEBUG=1`).
- **AP-15 / NO-CDN auf Linux (adaptiv):** Installation versucht zuerst **strikt
  offline** aus `wheels/` (`--no-index`-Dry-Run-Probe, kein Netz). Deckt das
  Wheelhouse die Plattform ab → Offline-Install; sonst — z. B. die gebundelten
  `win_amd64`/cp314-Wheels auf Linux — **lauter** Fallback auf Online-pip (kein
  stilles Nachladen). Schaltet automatisch auf offline, sobald ein passendes
  Linux-Wheelhouse vorliegt.

### Behoben

- **Leeres venv galt fälschlich als „vollständig":** `pip check` allein ist auf
  einem frisch gebauten, paketleeren venv vacuously grün — in Kombination mit
  einem noch passenden `.req_stamp` wäre der Install übersprungen worden (App
  hätte beim Import gecrasht). Der Vollständigkeits-Check prüft jetzt zusätzlich
  das tatsächliche Vorhandensein der Requirements. **Hinweis:** dieselbe latente
  Schwäche steckt in `run.ps1` (Windows) — dort zur Behebung vorgemerkt (Skript
  ist signiert, separate Session).

## [0.10.0] — 2026-06-26

### Hinzugefügt

- **AP-20 — Copy-Icon am SELECT:** In der oberen rechten Ecke des generierten
  SELECT sitzt ein Copy-Icon; ein Klick kopiert das SQL in die Zwischenablage
  (`navigator.clipboard`) mit kurzem „kopiert"-Feedback.

### Behoben

- **AP-21 — Kosmetik:** Der „Schema-Graph"-Balken (`.panelhead`) und die Tab-Linie
  (`.tabbar`) haben jetzt exakt dieselbe Höhe (gemeinsame `min-height` +
  `box-sizing`), vorher war der Graph-Balken minimal höher.

## [0.9.0] — 2026-06-26

### Geändert

- **AP-12 (Backend) — MS SQL Server: ODBC-Treiber & Verschlüsselung
  konfigurierbar, klare Treiber-Fehlermeldung:** `build_url` nutzt jetzt
  standardmäßig den aktuellen **ODBC Driver 18 for SQL Server** (überschreibbar
  per `driver`) und unterstützt optionale `Encrypt`/`TrustServerCertificate`-
  Parameter — nichts Unsicheres wird per Default angenommen. Fehlt der ODBC-
  Treiber, meldet die App das klar (AP-2-Stil) statt einer rohen pyodbc-Exception
  (`_odbc_driver_hint`: IM002 / „no default driver" / „Can't open lib"). Installations-
  Doku ergänzt. 118 Tests grün. (Realer Integrationstest gegen eine MSSQL-Instanz
  und UI-Felder für Encrypt/Trust folgen separat.)

## [0.8.0] — 2026-06-26

### Geändert

- **AP-15 (Teil 1, Windows) — `run.ps1` abbruchsicher + idempotent:** Der
  Windows-Launcher heilt sich nach abgebrochenen Läufen selbst. Jeder Schritt
  prüft seine Vorbedingungen (Python, venv-Integrität per Funktionstest,
  Paket-Vollständigkeit per `pip check`, freier Port) und zieht nur Fehlendes
  nach; der Requirements-Stamp wird erst nach erfolgreichem Install geschrieben
  (atomar). **NO-CDN / nur lokale Sourcen:** Installation strikt `--no-index`
  aus `wheels\` mit `--dry-run`-Vorabprüfung — fehlt ein Wheel, steigt das Setup
  mit Protokoll (welche Pakete fehlen) aus, **ohne etwas zu installieren oder
  online nachzuladen**. Neu außerdem: durchgängige Status-Ausgaben, Port-Check
  vor App-Start (5057 belegt → klare Meldung) und ein gegen Einzelfehler robustes
  Menü. Verifiziert: idempotenter Lauf, fehlender Stamp, fehlendes Wheel, belegter
  Port. (`run.sh`/Linux-Parität folgt separat.)

## [0.7.0] — 2026-06-26

### Hinzugefügt

- **AP-13 — UI-Politur:** Drei Verbesserungen in Objekt-Browser und Graph-Panel:
  (1) **Suchfeld** über dem Objekt-Browser filtert die Tabellen-/View-Listen live
  nach Namen; (2) **linker Splitter** macht die Sidebar-Breite per Drag verschiebbar
  (analog zum Graph-Splitter, via `--sidebar-width`); (3) **„Neu anordnen"-Button**
  im Graph-Panel würfelt das cose-Layout neu, dessen Abstände jetzt für dichte
  Schemas (> 12 Knoten) hochskalieren, damit Knoten weniger überlappen. Reines
  Frontend (`index.html`/`app.js`/`app.css`). Im Browser verifiziert (Playwright);
  115 Tests grün.

## [0.6.0] — 2026-06-26

### Hinzugefügt

- **AP-10 — Gespeicherte Verbindungen in der Topbar:** Neues Dropdown in der
  Topbar (neben „Verbinden") listet die in `config.json` gespeicherten
  Verbindungen; eine Auswahl verbindet sofort — passwortlose Verbindungen
  (SQLite oder Server ohne Auth) direkt, sonst öffnet sich der Verbindungs-Tab
  vorbefüllt zum Ergänzen des Passworts. Beide Verbindungs-Picker (Topbar +
  Verbindungs-Tab) teilen dieselbe Liste und spiegeln die Auswahl. Ein
  Verbindungswechsel setzt den UI-Zustand zurück (Detail-Tabs schließen,
  Graph-Highlight/UML-Karten leeren, Schema neu laden). Reines Frontend
  (`index.html`/`app.js`/`app.css`); die `/api/connections`-API blieb unverändert.
  Im Browser verifiziert (Playwright/Chromium); 114 Tests grün.

## [0.5.0] — 2026-06-26

### Geändert

- **AP-11 — Composite Foreign Keys voll unterstützt:** Mehrspaltige FKs werden
  nicht mehr nur auf dem ersten Spaltenpaar gejoint. Ein FK trägt jetzt alle
  `(lokal, referenziert)`-Spaltenpaare (`ForeignKey.column_pairs`, mit Properties
  `columns`/`ref_columns`/`is_composite`); der Join-Pfad-Generator emittiert
  `JOIN … ON a.x = b.x AND a.y = b.y`. Zwei **separate** einspaltige FKs zwischen
  denselben Tabellen bleiben weiterhin alternative Join-Wege (nicht mit AND
  verschmolzen). Betroffen: Loader, FK-Graph (`JoinEdge`), Pathfinder
  (`JoinStep.column_pairs`), SQL-Generator, DDL-Ansicht und `/api/schema`
  (FKs jetzt als `columns`/`ref_columns`-Listen, Frontend angepasst). 112 Tests grün.

## [0.4.0] — 2026-06-26

### Geändert

- **AP-14 — Python-3.14-Readiness (Windows):** Das Offline-Wheelhouse (`wheels/`)
  wurde von der CPython-3.12- auf die **3.14-ABI** umgestellt. Die fünf
  kompilierten Wheels (SQLAlchemy, psycopg2-binary, pyodbc, greenlet, MarkupSafe)
  liegen jetzt als `cp314-win_amd64` vor — identische Paketversionen, nur neuer
  ABI-Tag; die `py3-none-any`-Wheels bleiben versionsunabhängig. Die Launcher
  `run.ps1` (Offline-Gate) und `run.sh` (Präferenzreihenfolge) verlangen bzw.
  bevorzugen jetzt Python 3.14; `wheels/README.md` entsprechend aktualisiert.
  Verifiziert: venv mit Python 3.14.6, Offline-Setup aus `wheels/`, `pip check`
  sauber, alle **111 Tests grün**, App startet (HTTP 200).

## [0.3.1] — 2026-06-26

### Geändert

- **AP-9 — Ergebnisliste maximiert**: Die Ergebnistabelle unter dem Join-Builder
  nutzt jetzt den vollen vertikalen Restplatz nach unten (fixe `max-height: 320px`
  entfernt). Das Join-Builder-Panel ist eine Flex-Spalte; `#join_result` wächst
  mit (`flex: 1`, eigener Scroll). Auf das Join-Builder-Panel beschränkt, sodass
  Detail-Tabs ihren normalen Fluss behalten.

## [0.3.0] — 2026-06-26

### Hinzugefügt

- **AP-6 — Ausgabe-Steuerung im Join-Builder**: Auswahl der Ausgabezeilen
  (200 / 400 / Alle) plus „Aktualisieren"-Button im Ergebnisbereich.
  `/api/joinpath/run` akzeptiert nun `max_rows`; der Wert wird serverseitig auf
  `config.MAX_RESULT_ROWS` (5000) geklemmt — „Alle" heißt „alle bis zur
  Obergrenze" zum Schutz der Oberfläche. Die Antwort liefert `row_cap`; die
  Info-Zeile zeigt „N Zeilen (begrenzt auf …)". „Aktualisieren" liest das
  Formular neu (geänderte Sortierungen/Spalten) und behält den gewählten Pfad;
  ein Zeilenwechsel führt nur das aktuelle SELECT neu aus. Der hervorgehobene
  Join-Pfad im Graphen bleibt stabil, da Sortierungen/Zusatzspalten auf die
  Pfad-Tabellen beschränkt sind.
- **AP-7 — Feiner Graph-Zoom + Slider**: Mausrad-Zoom feinstufig
  (`wheelSensitivity` 0.2 statt 1, Zoom-Grenzen 10 %–400 %) plus vertikaler
  Zoom-Slider mit Prozent-Anzeige am rechten Graph-Rand, beidseitig
  synchronisiert (Scrollen ↔ Slider).

### Behoben

- **AP-8 — „Auswahl zurücksetzen"**: Der Button bereinigt jetzt zusätzlich den
  hervorgehobenen Join-Pfad im Graphen (`hl`) und schließt die UML-Karten
  darunter (`#uml_cards`) — vorher blieb beides stehen. Der interne
  Auswahl-Reset (neue Selektion starten) lässt die Karten bewusst bestehen.

## [0.2.0] — 2026-06-26

### Hinzugefügt

- **AP-5 — Tabellarischer Ausgabebereich im Join-Builder**: Beim Wählen eines
  Join-Pfads wird das generierte SELECT angezeigt **und** ausgeführt; die
  zurückgelieferten Zeilen erscheinen als Tabelle unter dem SQL. Neuer
  read-only Endpoint `POST /api/joinpath/run`: das SELECT wird **serverseitig**
  aus den validierten Join-Parametern erzeugt (kein client-geliefertes SQL),
  parametrisiert ausgeführt und auf max. 200 Zeilen begrenzt
  (`core.datapreview.execute_select`). Gemeinsame Pfad-/SQL-Bau-Logik in
  `_parse_joinpath_params` + `_make_path_gen` (von beiden Endpoints geteilt).

## [0.1.0] — 2026-06-25

### Hinzugefügt

- **FK-Graph** aus Live-DB-Reflection (SQLAlchemy, SQLite + PostgreSQL).
- **Join-Pfad-Builder** (k-kürzeste Pfade, deterministischer Tie-Break).
- **Filterobjekte** (WHERE über erreichbare Tabellen).
- **Read-only SQL-Generierung** mit parametrisierten Platzhaltern.
- **Flask-Web-UI** mit lokal gebundelten Assets.
- **Portable Demo-CMDB** (`sample_data/`): SQLite-DB + reproduzierbarer Generator,
  deckt mehrdeutige Pfade (Diamant), zusammengesetzte FKs, Graph-Sonderfälle
  (Selbstreferenz, Mehrfach-FK, isolierte Tabelle) und realistische Daten ab;
  inkl. Integrationstests pro Fall.
- **Interaktives Menü** in `run.sh` (ohne Argument) plus `run.ps1` für Windows mit
  identischem Menü; Flags (`--skip-setup` etc.) bleiben Hub-kompatibel.
- **Filter-UI**: „Filter +" fügt Filterzeilen hinzu (Tabelle · Spalte · Operator ·
  Wert · Entfernen); mehrere Filter werden mit UND verknüpft und an die
  bestehende, getestete Backend-Filterlogik (parametrisiertes WHERE) gesendet.
- **Graph-Visualisierung**: neuer `/api/graph`-Endpoint (Knoten/Kanten) und eine
  interaktive Schema-Graph-Ansicht mit Cytoscape.js (lokal gebundelt, kein CDN).
  Der gewählte Join-Pfad wird im Graph farblich hervorgehoben; die
  joinpath-Antwort liefert die konkreten Pfad-Kanten.
- **Implizite (geratene) Foreign Keys**: optionale Heuristik (Spaltenname trifft
  einspaltigen Primärschlüssel einer anderen Tabelle, kompatibler Typ).
  Per Checkbox einschaltbar; gefundene Beziehungen erscheinen im Graph
  gestrichelt und ermöglichen Join-Pfade auch ohne deklarierte FKs. Neue
  FK-lose Demo-DB (`demo_cmdb_nofk.db`) zum Ausprobieren.
- **Verbindungs-Manager** (Tools → Verbindungen): strukturiertes Formular mit
  Datenbank-Typ-Auswahl (SQLite, PostgreSQL, MySQL/MariaDB, MS SQL Server) und
  passenden Feldern. Das Backend baut die SQLAlchemy-URL (`core.connection.build_url`)
  und testet die Verbindung (`/api/connect`). Benannte Verbindungen speicherbar
  in `config.json` (ohne Passwort).

### Geändert

- **Info-Bereich** in der Sidebar ans untere Ende gesetzt; zeigt App-Metadaten und
  Technologie-Stack via `GET /api/info`.
- **3-Panel-Layout** (wie ein minimalistischer SQL Developer): Objekt-Browser links,
  Tab-Bereich Mitte, Schema-Graph rechts mit eigenem Scrolling.
- **Views** werden reflektiert; `/api/schema` liefert Spalten + SQL-Definition.
- **Detail-Tabs**: „Definition", „Daten" (Vorschau erste 100 Zeilen via `/api/data`),
  „SQL" (rekonstruiertes DDL).
- **UX**: Connection-URL aus `default_connection` vorbelegt — Demo-DB direkt startbereit.

### Bekannte Einschränkungen

- **Composite Foreign Keys**: Schemas mit Mehrspaltigen FKs werden in v1 nur auf der
  ersten Spalte gejoint; einspaltigen FKs sind vollständig unterstützt.
- **Datenbank-Backends**: PostgreSQL-Support ist implementiert, aber in der
  automatisierten Testsuite nur gegen SQLite abgedeckt.
