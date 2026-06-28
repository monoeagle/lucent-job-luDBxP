# Insight: Ein Feature für die Doku „echt benutzen" ist ein hochwirksamer Bug-Detektor

**Datum:** 2026-06-29 (Session 14)
**Auslöser:** Zweimal in einer Session deckte das **Erzeugen von Screenshots / das reale Bedienen** eines Features einen latenten Bug auf, den die Unit-Tests nicht fingen.

## Die zwei Fälle

1. **AP-64 (Verbindungsform):** Beim Screenshot-/Smoke-Bau für den neuen „Testen"-Button stellte sich heraus, dass ein **unerreichbarer Oracle-Host** `/api/connect` → **HTTP 500** liefert (statt 400), weil der oracledb-Treiber eine Exception wirft, die der Loader (`except SQLAlchemyError`) nicht fängt. „Testen" zeigte dann eine generische statt der echten Meldung — genau im Hauptanwendungsfall des Buttons.
2. **HAVING-Klausel (SQL-Builder):** Beim Aufnehmen des Beispiel-Screenshots „Aggregat + HAVING" lieferte die read-only Vorschau **0 Zeilen**, obwohl das generierte SQL korrekt war: der HAVING-Wert wurde als **String** `'1'` gebunden; ein Aggregat-Ausdruck hat keine Spalten-Affinität, also vergleicht SQLite `COUNT(int) > '1'` (Text) nie gleich → alle Gruppen fielen still raus.

## Warum die Tests es nicht fingen

- **AP-64:** Es gab keinen Test gegen einen echten unerreichbaren Host (zu langsam/flaky für CI) — die Lücke lag genau im ungetesteten Live-Pfad.
- **HAVING:** Die bestehenden sqlgen-Tests übergaben den Vergleichswert als **`int`** (`Having(..., ">", 5)`). Der Bug entsteht nur mit dem **String** aus dem Formular (`"5"`) — der Pfad, den ein echter Nutzer nimmt, war im Test nicht abgebildet. Zusätzlich maskierte SQLites Typaffinität das Problem für WHERE-auf-Spalten, sodass es nur bei HAVING-auf-Aggregat auftrat.

## Die Lehre

**Wer ein Feature dokumentiert/screenshotet, soll es dabei *real gegen die laufende App* bedienen — nicht nur dem Code/den grünen Tests vertrauen.** Das visuelle/manuelle Durchspielen trifft genau die Eingaben und Pfade, die Unit-Tests gern abkürzen (Formular-Strings statt typisierter Werte, Fehlerfälle gegen echte Treiber, Leerzustände der UI). Beide Bugs wären sonst erst beim Nutzer aufgefallen.

Praktischer Reflex:
- Beim Screenshot-/Smoke-Bau bewusst auch **Fehler- und Leerzustände** ansteuern (kaputte Verbindung, leere Box, Wert-Grenzfälle), nicht nur den Happy Path.
- Wenn ein Wert aus dem Formular kommt, im Test **denselben Typ** (String) verwenden, den der Nutzer schickt — nicht den schon typisierten Wert.
- Stille Null-/Leerergebnisse sind verdächtig: „korrektes SQL, aber 0 Zeilen" war hier das Symptom eines Binding-Typ-Bugs.

Verwandt: dieselbe „immer prüfen, nie raten / gegen den echten Code verifizieren"-Disziplin, hier auf die **Laufzeit** angewandt. Auch die SQL-Box-Politur dieser Session (leerer Ausgabe-`<pre>` → schmaler Streifen, Copy-Icon halb abgeschnitten) fiel nur im **gerenderten Leerzustand** auf, nicht im Markup.
