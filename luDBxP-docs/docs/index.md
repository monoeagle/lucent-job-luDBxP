<div class="adb-home-layout">

<div class="adb-home-arch adb-home-arch--split">
  <div class="adb-home-arch__main">
    <img src="images/mermaid/entwicklung-arbeitspakete-1.svg" alt="Arbeitspakete — thematischer Baum mit Abhängigkeiten (grün = erledigt, blau = geplant)">
  </div>
  <div class="adb-home-arch__band adb-ap-match">
    <table class="adb-ap-match-table">
      <thead><tr><th colspan="2">📑 AP-Matching · Kurzbeschreibung</th></tr></thead>
      <tbody>
        <tr class="grp"><td colspan="2">⚙️ Engine / Fundament</td></tr>
        <tr><td>AP-11</td><td>Composite-FK: ON … AND …</td></tr>
        <tr class="grp"><td colspan="2">🔌 Verbindungen & Backends</td></tr>
        <tr><td>AP-2</td><td>Verbinden-Fehler entschärft</td></tr>
        <tr><td>AP-10</td><td>Verbindungen in der Topbar</td></tr>
        <tr><td>AP-12</td><td>MSSQL real testbar</td></tr>
        <tr><td>AP-22</td><td>Implizite FKs (opt-in)</td></tr>
        <tr class="grp"><td colspan="2">🧩 Join-Builder & SQL-Ausgabe</td></tr>
        <tr><td>AP-3</td><td>SQL-Optionen: DISTINCT/ORDER BY/LIMIT/IN</td></tr>
        <tr><td>AP-4</td><td>Mehrere SELECT-Spalten</td></tr>
        <tr><td>AP-5</td><td>Ausgabebereich: SELECT → Tabelle</td></tr>
        <tr><td>AP-6</td><td>Ausgabe-Steuerung: Zeilen/Refresh</td></tr>
        <tr><td>AP-9</td><td>Ergebnisliste maximiert</td></tr>
        <tr><td>AP-20</td><td>Copy-Icon am SELECT</td></tr>
        <tr><td>AP-23</td><td>Join-Maske vereinheitlicht</td></tr>
        <tr><td>AP-25</td><td>SQL-Statement-Analyzer</td></tr>
        <tr><td>AP-29</td><td>SQL-Dialekt umschalten</td></tr>
        <tr><td>AP-30</td><td>N-1-Stern (mehrere Lookup-Ziele)</td></tr>
        <tr><td>AP-36</td><td>Fan-out-Richtung pro Join (N-1/1-N)</td></tr>
        <tr><td>AP-37</td><td>Start⇄Ziel-Tausch</td></tr>
        <tr><td>AP-38</td><td>Kopierbares lauffähiges SQL</td></tr>
        <tr><td>AP-39</td><td>SQL-Analyzer vertieft (Struktur/Lints)</td></tr>
        <tr><td>AP-40</td><td>Graph-Legende + Marker-Fix</td></tr>
        <tr><td>AP-41</td><td>Join-Typ pro Schritt (LEFT/RIGHT/FULL)</td></tr>
        <tr><td>AP-42</td><td>Join-Builder-Politur</td></tr>
        <tr><td>AP-43</td><td>Lesbares mehrzeiliges SQL-Layout</td></tr>
        <tr><td>AP-44</td><td>Kompakter + NULL/Status</td></tr>
        <tr><td>AP-45</td><td>Spaltenkopf-Aktionen + Filter-DISTINCT</td></tr>
        <tr><td>AP-46</td><td>Detailkarten folgen der Auswahl</td></tr>
        <tr><td>AP-47</td><td>Pfad-Indikator + Waisen-Chip</td></tr>
        <tr><td>AP-48</td><td>Analyzer-Textbox + Tippfehler-Lint</td></tr>
        <tr><td>AP-49</td><td>Analyzer-Feinschliff + ANSI-Fix</td></tr>
        <tr class="grp"><td colspan="2">🕸️ Graph-Visualisierung</td></tr>
        <tr><td>AP-1</td><td>Graph-Interaktion: UML-Karte → Pfad</td></tr>
        <tr><td>AP-7</td><td>Feiner Graph-Zoom</td></tr>
        <tr><td>AP-8</td><td>Fix Auswahl-Reset</td></tr>
        <tr><td>AP-13</td><td>UI-Politur: Suchfeld/Splitter/Re-Layout</td></tr>
        <tr><td>AP-16</td><td>dagre-Layout (minimale Kreuzungen)</td></tr>
        <tr><td>AP-21</td><td>Kosmetik: Balkenhöhe</td></tr>
        <tr><td>AP-28</td><td>Scroll nur im Ergebnis</td></tr>
        <tr><td>AP-32</td><td>Zoom-Slider in der Kopfzeile</td></tr>
        <tr class="grp"><td colspan="2">🗂️ Daten & UI-Rahmen</td></tr>
        <tr><td>AP-18</td><td>Multi-Tabellen-Join</td></tr>
        <tr class="grp"><td colspan="2">🚀 Deployment & Betrieb</td></tr>
        <tr><td>AP-14</td><td>Python-3.14 / AppImage</td></tr>
        <tr><td>AP-15</td><td>abbruchsicher + idempotent</td></tr>
        <tr><td>AP-31</td><td>Terminal-Server (Multi-User)</td></tr>
        <tr><td>AP-33</td><td>Logging sauber</td></tr>
        <tr><td>AP-34</td><td>Tray-Icon-Launcher</td></tr>
        <tr><td>AP-35</td><td>run.ps1: leeres venv-Fix</td></tr>
        <tr class="grp"><td colspan="2">📚 Doku & Prozess</td></tr>
        <tr><td>AP-19</td><td>.pattern_transfer</td></tr>
        <tr><td>AP-24</td><td>Session-KPIs (dev-intern)</td></tr>
        <tr><td>AP-26</td><td>Audit-Sessions</td></tr>
        <tr><td>AP-27</td><td>Insights</td></tr>
      </tbody>
    </table>
  </div>
</div>

<div class="adb-home-footer">
  <section class="adb-home-footer__col" data-adb-home-col="heatmap">
    <h3 class="adb-home-footer__title">Aktivität (365 Tage)</h3>
    <div data-adb-activity-heatmap></div>
  </section>

  <section class="adb-home-footer__col" data-adb-home-col="insights">
    <h3 class="adb-home-footer__title">Insights</h3>
    <div data-adb-activity-stats></div>
  </section>
</div>

</div>

<div data-adb-activity-detail style="display:none"></div>
