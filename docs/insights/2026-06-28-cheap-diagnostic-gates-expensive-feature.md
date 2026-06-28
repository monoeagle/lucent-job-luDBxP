# Insight — Ein billiges Diagnose-AP vor das teure stellen

**Datum:** 2026-06-28 (Session 12)
**Kontext:** Cross-Schema-Joins (AP-57) sind die größte verbleibende Reflection-Stufe — ein **XL**-Datenmodell-Umbau quer durch Model/Loader/Graph/Pathfinder/sqlgen/UI, real nur gegen ein echtes Postgres/Oracle/MSSQL verifizierbar.

## Beobachtung

Statt AP-57 direkt zu bauen, wurde zuerst **AP-54 (Cross-Schema-FK-Diagnose, Aufwand S)** gebaut: `referred_schema` ins Model tragen (wurde bisher verworfen), die Cross-Schema-Kanten ableiten und im Info-Panel anzeigen. Das beantwortet **empirisch** die einzige Frage, die über AP-57 entscheidet: *„Hat die Ziel-DB (HCMX) überhaupt FKs über Schema-Grenzen?"*

Erwartete Antwort für HCMX: **nein** (die Suite koppelt Produkte über REST/fachliche IDs, nicht über referenzielle Integrität). Dann entfällt AP-57 ganz — XL gespart durch S.

## Die Lehre

**Vor einem teuren, schwer testbaren Feature erst eine billige, read-only Diagnose bauen, die empirisch entscheidet, ob das teure Feature überhaupt gebraucht wird.** Das Diagnose-AP ist günstig, sofort testbar (hier: Unit-Tests mit konstruierten Model-Objekten, auch wenn die Live-Reflexion ein echtes Backend bräuchte), und liefert dem Nutzer eine Entscheidungsgrundlage statt einer Annahme.

## Warum das zählt

- **Annahmen kosten am meisten beim teuersten Feature.** Ein spekulativ gebautes XL-Feature, das sich als unnötig herausstellt, ist der teuerste Fehlgriff. Eine S-Diagnose davor ist eine Versicherung mit minimaler Prämie.
- **Es macht „bedingt/zurückgestellt" konkret.** AP-57 ist im Backlog explizit als *„nur bauen, wenn AP-54 echte Cross-Schema-FKs nachweist"* markiert — das Gate ist nicht vage, sondern ein messbares Signal.
- **Es passt zum Reverse-Engineering-Zweck des Tools:** Die ehrlichste Antwort auf „brauchen wir X?" kommt aus der echten DB, nicht aus dem Bauchgefühl — und genau das liefert eine Diagnose-Scheibe.

## Anwendung

Bei jeder „große Stufe vs. unsicherer Bedarf"-Situation prüfen: *Gibt es eine kleine, read-only Messung, die den Bedarf empirisch klärt?* Wenn ja, diese zuerst bauen und das große AP daran gaten. Verwandt mit der globalen Konvention „Spec gegen den echten Code prüfen, bevor geplant wird" — hier: **Bedarf gegen die echten Daten prüfen, bevor das teure Feature gebaut wird.**
