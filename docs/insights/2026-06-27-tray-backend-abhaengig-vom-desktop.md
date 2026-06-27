# Insight — GUI-/Desktop-Integration ist umgebungsabhängig: headless „importiert" ≠ „funktioniert"

**Datum:** 2026-06-27 (Session 8, AP-34 v0.34.1) · Kontext: pystray-Tray-Icon auf Linux

## Erkenntnis

Ein „Import klappt headless"-Smoke-Test beweist **nicht**, dass eine GUI funktioniert. Bei AP-34
baute `build_tray()` headless sauber durch — aber auf dem echten Linux-Desktop zeigte das
Tray-Icon **kein Kontextmenü**. Ursache war das **Backend**: ohne PyGObject fällt pystray auf
das `_xorg`-Backend zurück, und dessen `HAS_MENU = False`/`HAS_NOTIFICATION = False` — Icon ja,
Menü/Notifications nein. Das menüfähige AppIndicator/GTK-Backend braucht PyGObject.

Zweite, fiese Schicht: **ABI-Mismatch**. Die *systemweite* PyGObject ist für die OS-Python (3.12)
kompiliert; das Projekt-venv ist 3.14. `import gi` aus dem venv scheiterte mit
`cannot import name '_gi'` — die kompilierte Extension passt nicht über Minor-Versionen. Lösung:
PyGObject **im venv** bauen (`PyGObject<3.52` wegen girepository-1.0; `libgirepository1.0-dev` +
`gobject-introspection` per apt). Danach wählt pystray automatisch `_appindicator`
(HAS_MENU=True).

## How to apply

1. **GUI nicht nur per Import smoke-testen.** „Importiert + Objekt gebaut" ist ein schwaches
   Signal; die eigentliche Funktion (Menü, Fenster, Tray) muss am **realen Desktop** geprüft
   werden — oder explizit als „nur dort verifizierbar" markiert (so stand es korrekt in der
   AP-34-Spec; der Nutzer fand die Lücke beim ersten echten Klick).
2. **Backend-Fähigkeiten abfragen, nicht annehmen.** Bibliotheken mit pluggable Backends
   (pystray, …) haben Capability-Flags (`HAS_MENU` etc.) — die sagen die Wahrheit über die
   *aktuelle* Umgebung.
3. **System-Pakete ≠ venv-Pakete bei C-Extensions.** PyGObject/pycairo & Co. müssen für die
   **venv-Python-Version** vorliegen; system-site-packages über Minor-Versionen hinweg
   funktionieren nicht. Optionale, plattformspezifische GUI-Deps **getrennt** halten
   (`requirements-tray-linux.txt`), damit ein fehlgeschlagener GUI-Build nie den Kern-Install bricht.

## Übergeordnet

Verlängert „Spec gegen den echten Code prüfen" um **„Feature gegen die echte Laufzeitumgebung
prüfen"** — gerade bei Desktop-/Plattform-Integration, wo dieselbe Code-Zeile je nach
installiertem Backend/Toolkit unterschiedlich (oder gar nicht) wirkt.
