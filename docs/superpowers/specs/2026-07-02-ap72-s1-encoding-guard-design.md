# AP-72·S1 — Encoding-Hygiene-Guard (UTF-8 / kein BOM / kein Mojibake)

**Datum:** 2026-07-02 · **Status:** Design (Review offen) · **Version-Ziel:** v0.68.1 (patch, reiner Test)

## Befund / Umscope

Die ursprüngliche AP-72·S1-Idee war „repo-weit Mojibake bereinigen". **Verifikation gegen den echten
Code:** das Repo ist bereits **mojibake- und BOM-frei** (`git ls-files` über alle Code-Endungen → 0
echte Treffer; das echte `app.py` = 0, im Gegensatz zum nie committeten Nutzer-Draft). Die einzigen
2 Marker-Treffer stehen in `luDBxP-docs/docs/projekt/roadmap.md` und sind **absichtliche
Beispiel-Strings** (die AP-72-Beschreibung selbst nennt `â†'`/`Ã¼` als zu vermeidende Muster).

→ Es gibt **nichts zu bereinigen**. AP-72·S1 wird auf **Prävention** umgescopt: ein Guard-Test, der
künftiges Mojibake/BOM/Nicht-UTF-8 in Code-Dateien abfängt.

## Scope (YAGNI)

**In Scope:** ein pytest-Test, der getrackte **Code**-Dateien auf UTF-8-Gültigkeit, fehlendes BOM und
Abwesenheit von Doppelkodierungs-Sequenzen prüft. **Out of Scope:** jede Datei-Reparatur (nichts
kaputt); Laufzeit-UTF-8 (`PYTHONUTF8`/`reconfigure`) = AP-72·S2; Markdown/Doku-Prüfung (dürfen solche
Beispiel-Strings legitim tragen).

## Design

**Komponente:** neue Datei `tests/test_encoding_hygiene.py`. Kein Produktionscode ändert sich.

### Datei-Auswahl
- Quelle: `git ls-files` (subprocess) → exakte Menge getrackter Dateien, kein manuelles Exclude-Pflegen.
- Filter: Endungen `.py`, `.js`, `.html`, `.css`, `.sh`, `.ps1`.
- Ausschluss (generiert): Pfade unter `luDBxP-docs/site/` und `build/`.
- Kein Git-Repo / `git`-Aufruf schlägt fehl → `pytest.skip("kein git-Repo")`.

### Drei Prüfungen je Datei
1. **Kein BOM** — Datei-Bytes beginnen nicht mit `b"\xef\xbb\xbf"`.
2. **Gültiges UTF-8** — `raw.decode("utf-8")` wirft nicht (sonst Fehler mit Dateiname + Position).
3. **Kein Mojibake** — Regex auf dem dekodierten Text: `[ÂÃâ][-¿]`
   (die Doppelkodierungs-Signatur: `Ã…`, `â€…`, `Â…`). Echte deutsche UTF-8-Zeichen (`ü`=U+00FC,
   `ä`=U+00E4 …) matchen nicht, da sie nicht aus `Â/Ã/â` + Fortsetzungs-Byte-Bereich bestehen.

### Selbst-Referenz-Falle
Die Regex-Muster werden aus **Unicode-Escapes** (`"Ã"` …) zusammengesetzt, damit die Test-Datei
selbst reines ASCII bleibt und sich nicht selbst als Mojibake flaggt.

### Fehlerbericht
Bei Verstoß: Assertion-Message mit **Datei : Zeilennummer : gefundene Sequenz** je Treffer, damit der
Fund direkt lokalisierbar ist. Ein Test sammelt alle Verstöße und schlägt einmal gebündelt fehl
(kein Abbruch beim ersten), damit der volle Umfang sichtbar ist.

### Struktur
Ein Test `test_source_files_are_clean_utf8` mit drei Helfern: `_tracked_code_files()` (git ls-files +
Filter), `_MOJIBAKE_RE` (aus Escapes), und eine Schleife, die BOM/Decode/Mojibake sammelt.

## Testing
Der Test IST das Deliverable. Verifikation, dass er wirklich greift: temporär eine Datei mit
bekanntem Mojibake in die geprüfte Menge einschleusen (Monkeypatch der Datei-Liste um einen
tmp-Pfad) → Test rot; ohne den tmp-Pfad → grün. Damit ist bewiesen, dass der Guard nicht nur
tautologisch grün ist.

## Release
Reiner Test, kein Verhalten. `sync_version.py --patch` → **v0.68.1**; Changelog EN + DE; icon-rail
`TEST_COUNT` (466 → neue Zahl); Roadmap AP-72·S1 → done (`roadmap_data.py` + `roadmap.md`-Prosa +
`.mmd` B10 done); Whole-Branch-Review; Site + gh-pages.

## Offene Punkte für den Review
- Endungs-Scope bewusst auf Code beschränkt (`.toml/.yml/.json` ausgenommen — enthalten keine
  Freitext-Sonderzeichen, geringes Risiko). Änderbar.
