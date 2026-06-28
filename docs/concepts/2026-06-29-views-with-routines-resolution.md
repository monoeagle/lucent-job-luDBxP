# Konzept & Arbeitspaket — Views, die Prozeduren/Funktionen verwenden (AP-66)

**Datum:** 2026-06-29
**Status:** Konzept / Backlog (AP-66)
**Auslöser:** Frage aus dem Migrations-Kontext: *Was ist, wenn in den Views auch Prozeduren und Funktionen benutzt werden? Wie werden diese aufgelöst?* HCM(X) läuft auf **Oracle**-DBs, wo Views regelmäßig **PL/SQL-Funktionen** (auch aus Packages) aufrufen.

## 1. Problem

Eine View ist nicht zwingend „nur ein gespeicherter SELECT über Tabellen". In Oracle (und teils anderen DBs) kann eine View-Definition **Funktionen/Prozeduren** aufrufen — skalare PL/SQL-Funktionen, Package-Functions, deterministische oder Table-/Pipelined-Functions. Dann steckt ein Teil der **Datenlogik in der Routine**, nicht in Joins/FKs.

Für das Reverse-Engineering/Migrations-Ziel heißt das: solche Views sind **nicht 1:1 über reine Join-/FK-Lineage** nachvollziehbar oder migrierbar — die Logik der referenzierten Routine muss erkannt und (in der ETL/Zielschicht) nachgebaut werden. Das Werkzeug sollte daher zumindest **sichtbar machen**, welche Views auf Routinen beruhen.

## 2. Code-Befund (Ist-Stand verifiziert)

- `core/loaders/sqlalchemy_loader.py:98–108`: Views werden über `insp.get_view_names()` + `insp.get_view_definition(vname)` reflektiert und als `View(name, columns, definition)` abgelegt — der **Definitionstext ist roh** (String), Spalten kommen aus der Reflection. **Es findet keine Auflösung statt:** in der View referenzierte Funktionen/Prozeduren werden nicht erkannt, nicht verlinkt, nicht reflektiert.
- `core/model.py::View` hält `name`, `columns`, `definition` — kein Feld für referenzierte Routinen.
- Verwandt, aber getrennt: **AP-63 · Stufe 3** plant, **Stored Procedures + Functions (+ Oracle Packages/Synonyms)** als eigene Objekt-Kategorie read-only zu reflektieren (Quelltext/Signatur). AP-66 baut darauf auf, fokussiert aber auf die **Beziehung View → Routine** und deren Migrations-Bedeutung.

## 3. Was ich tun würde (gestuft)

**Stufe 1 — Diagnose: „nutzt Routine X" sichtbar machen (billig, größter Sofortnutzen):**
- Aus dem (bereits vorhandenen) View-`definition`-Text die **referenzierten Funktions-/Prozedur-Namen extrahieren** — per sqlglot-AST (`exp.Anonymous`/Funktionsaufrufe, gefiltert gegen bekannte SQL-Built-ins) bzw. konservativ per Heuristik. Bekannte Aggregat-/Built-in-Funktionen ausschließen, sodass nur **benutzerdefinierte** Routinen übrig bleiben.
- Im **View-Detail** anzeigen: „Diese View verwendet Funktion(en): …" + Markierung der View in der Übersicht („beruht auf Routinen-Logik"). Read-only, keine Auflösung der Routine selbst.
- **Migrations-Mehrwert:** liefert direkt die Liste der Views, die **nicht** über reine Join/FK-Lineage migrierbar sind — der eigentliche Knackpunkt für „sauberer Export".

**Stufe 2 — Routine reflektieren (Quelltext/Signatur):**
- Die referenzierten Routinen selbst reflektieren (über AP-63·S3-Mechanismus): Oracle-Katalog `ALL_PROCEDURES`/`ALL_ARGUMENTS`/`ALL_SOURCE` (bzw. `USER_SOURCE`), Package-Auflösung. Im View-Detail die **Signatur + Quelltext** der genutzten Routine verlinkt anzeigen.
- Pro Dialekt unterschiedlich; nur **live** testbar (Oracle/PG/MSSQL), nicht in SQLite-CI.

**Stufe 3 — Daten-Lineage durch die Routine (zurückgestellt):**
- Nachvollziehen, **welche Tabellen/Spalten eine PL/SQL-Routine liest** (echte Lineage durch den Routinen-Body). Erfordert PL/SQL-Parsing — **sehr aufwendig**, dialekt-spezifisch, fehleranfällig. **XL / wahrscheinlich Nicht-Scope** — für die Migration genügt meist Stufe 1+2 (wissen, *dass* und *welche* Routine beteiligt ist, plus ihr Quelltext, um die Logik manuell nachzubauen).

## 4. Nicht-Scope

- Kein Ausführen/Auswerten von Prozeduren/Funktionen (Read-only-Invariante).
- Kein automatisches Übersetzen von PL/SQL in das Zielmodell — die Logik wird **angezeigt**, der Nachbau passiert in der ETL-/Zielschicht.
- Stufe 3 (echte Routinen-Lineage) ist bewusst zurückgestellt.

## 5. Aufwand, Abhängigkeit, Sequenzierung

- **Stufe 1:** **S–M** — Funktions-Namen-Extraktion aus dem View-Definitionstext (sqlglot) + Anzeige. Teilweise SQLite-testbar (Extraktion ist text-/AST-basiert), die Oracle-Spezifika nur live.
- **Stufe 2:** **M** — Routinen-Reflection, gekoppelt an **AP-63 · Stufe 3**; nur live testbar.
- **Stufe 3:** **XL**, zurückgestellt.
- **Abhängigkeit:** Oracle-Verbindung existiert (AP-53). Stufe 2 überlappt mit AP-63·S3.

**Empfehlung:** **Stufe 1 zuerst** — sie ist der billige Diagnose-Schnitt (analog zur AP-54-Logik „erst empirisch sichtbar machen, dann entscheiden") und beantwortet die migrations-relevante Frage „welche Views beruhen auf Routinen-Logik?" ohne die teure Routinen-Reflection.
