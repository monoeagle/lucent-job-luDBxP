# Insight — Scheiben nach Testbarkeit schneiden + synthetische Naht-Tests

**Datum:** 2026-06-29 (Session 15)
**Kontext:** 6 APs in einer Session (v0.49.0 → v0.54.0): AP-56b·Stufe 1+2, AP-56c, AP-63·S1/S2/S2b. Zwei davon (AP-63·S2/S2b) betrafen Objekte, die SQLite **nicht** kennt (Trigger nur via Katalog-SQL; Sequences/Materialized Views nur PG/Oracle).

## Erkenntnis 1 — Eine gebündelte AP nach **Testbarkeit** zuschneiden, nicht nach Thema

AP-63·S2 war im Backlog als „Sequences + Materialized Views + Triggers" gebündelt — thematisch eine Einheit („neue Sidebar-Kategorien"). Aber die drei Objekttypen haben **völlig verschiedene Reflektions- und Testbarkeits-Profile:**

| Typ | Reflektion | CI-testbar? |
|---|---|---|
| Trigger | dialekt-Katalog-SQL (`sqlite_master`) | **ja, SQLite** |
| Sequences | SQLAlchemy-nativ `get_sequence_names` | nein (PG/Oracle) |
| Materialized Views | SQLAlchemy-nativ `get_materialized_view_names` | nein (PG/Oracle) |

Statt alles zusammen (wobei 2/3 in CI ungetestet geblieben wären) wurde die erste Scheibe auf **Trigger** verengt — voll SQLite-CI-testbar, etabliert das Kategorie-Muster end-to-end. Sequences/Matviews wurden zu **AP-63·S2b** auf demselben, dann bewährten Muster.

**Lehre:** Die Scheiben-Grenze ist nicht das Thema, sondern **„was kann ich in CI grün beweisen?"**. Ein voll verifizierter Pfad, der das Muster etabliert, macht die nächste (unverifizierbare) Scheibe billig und risikoarm. Das ist die Verlängerung der Projekt-Disziplin „SQLite-CI-testbar zuerst".

## Erkenntnis 2 — Für nur-gegen-X-verifizierbare Features: **synthetische Daten an der Naht injizieren**

AP-63·S2b reflektiert echt nur gegen PostgreSQL. Trotzdem wurde die Scheibe **ohne PG vollständig in CI getestet**, durch ein Tripel synthetischer Naht-Tests:

1. **Endpoint (Serialisierung):** `SqlAlchemyLoader.load` per `monkeypatch` durch ein **konstruiertes `Schema`** mit einer Sequenz + einer Matview ersetzt → `/api/schema` serialisiert korrekt. (Die Naht: Loader → Endpoint.)
2. **UI (Rendering):** Playwright **`page.route("**/api/schema", …)`** fängt die echte Antwort ab und injiziert Fake-Sequenz/-Matview → Sidebar-Kategorien + Detail-Zweige rendern. (Die Naht: Endpoint → Browser.)
3. **Echter Reflect-Pfad:** ein **skip-guarded** Live-Test (`tests/test_pg_integration.py`, `LUCENT_PG_TEST_URL`) — läuft nur, wenn jemand eine PG-Instanz stellt; skippt sonst sauber.

So bleibt die ganze Verdrahtung (Model/Endpoint/Sidebar/Detail) **CI-grün beweisbar**; nur der unvermeidbar backend-spezifische Reflektions-Schritt ist skip-guarded. Kein „läuft schon, vertrau mir"-Code im Repo.

**Lehre:** Wenn ein Feature an einem nicht-verfügbaren Backend hängt, injiziere **synthetische Daten an der nächsten testbaren Naht** (Funktions-Monkeypatch, HTTP-Intercept) statt die Verifikation auf „nur live" zu verschieben. Der einzige skip-guarded Teil sollte der irreduzible backend-Schritt sein.

## Erkenntnis 3 — Modell-gestufte Subagenten-Fließband

6 APs liefen als gleichförmiges SDD-Fließband (Brainstorm → Spec → Plan → 4 Tasks → je Task-Review → Whole-Branch-Review → Release → Deploy). Die Modellwahl je Rolle hielt das billig:
- **haiku** für triviale Endpoint-Serialisierung (3–7 Zeilen + Test, vollständiger Code im Brief) — z. B. die `/api/schema`-Felder in AP-63·S1/S2/S2b.
- **sonnet** für Implementer mit Integration (Loader/Route/UI) + alle Task-Reviewer.
- **opus** nur für die 6 Whole-Branch-Final-Reviews (die das „andere Loader brechen?"-Risiko gegen *jeden* Konstruktor verifizierten).

**Wiederkehrendes Muster der Final-Reviews:** Bei jeder Model-Erweiterung (`Table.indexes/checks`, `Schema.triggers/sequences/materialized_views`) war die Kern-Frage „bricht das einen anderen positionalen Konstruktor?" — und die ehrliche Antwort kam nur aus dem **Durchgehen jedes `Schema(...)`/`Table(...)`-Konstruktors im Baum**. Trailing-Felder mit `()`-Default + Append-am-Ende war jedes Mal die sichere Form.
