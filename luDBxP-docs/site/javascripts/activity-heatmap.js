/* ─────────────────────────────────────────────────────────────────────────
   Activity-Heatmap — 53 Wochen × 7 Tage Grid analog GitHub-Contributions.
   Liest project-activity.json (von tools/Generate-ProjectActivity.ps1 erzeugt)
   und rendert in jeden Container mit data-adb-activity-heatmap="true".

   Color-Scale (GitHub-Style):
     0      → --adb-act-0  (grau)
     1–2    → --adb-act-1
     3–5    → --adb-act-2
     6–10   → --adb-act-3
     11+    → --adb-act-4  (dunkelgrün)

   Tooltip on hover zeigt: Datum, Commits-Anzahl, Top-Kind des Tages.
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  const DATA_URL = '../_data/project-activity.json';
  const FALLBACK_URLS = [
    './_data/project-activity.json',
    '/_data/project-activity.json',
    '../../_data/project-activity.json',
  ];

  // 7-stufige Buckets — Hintergrund (0) · Grau-Stufen (1-5) · Grün-Stufen
  // (6-20) · Rot-Stufen (21+). Schwellen vom User vorgegeben — die feine
  // Sub-Stufung erlaubt es, sowohl Routine-Tage als auch Peak-Tage zu
  // unterscheiden.
  function bucket(n) {
    if (!n) return 0;
    if (n <= 2)  return 1;   // 1–2   · Grau hell
    if (n <= 5)  return 2;   // 3–5   · Grau dunkel
    if (n <= 12) return 3;   // 6–12  · Grün hell
    if (n <= 20) return 4;   // 13–20 · Grün dunkel
    if (n <= 40) return 5;   // 21–40 · Orange/Rot hell
    return 6;                // 41+   · Rot dunkel
  }

  function fmtDate(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }

  // 10-Tage-Spalten (Dekaden) für ein 1-Jahres-Fenster (bis heute).
  // 365 / 10 = 36.5 → 37 Spalten, jede mit 10 Tagen. Damit kompakter als
  // klassische 7×53-Wochensicht und Wochentags-Muster werden geglättet,
  // weil die Spalten-Phase pro Spalte um 3 Tage verschoben ist.
  const ROWS_PER_COL = 10;
  function buildDecadeColumns(today) {
    const cols = [];
    // 36 Spalten + heutige (ggf. unvollständige) = 37
    const oldest = new Date(today);
    oldest.setDate(today.getDate() - 364);
    let cursor = new Date(oldest);
    while (cursor <= today) {
      const block = [];
      for (let d = 0; d < ROWS_PER_COL; d++) {
        if (cursor > today) {
          block.push(null);
        } else {
          block.push(new Date(cursor));
        }
        cursor.setDate(cursor.getDate() + 1);
      }
      cols.push(block);
    }
    return cols;
  }

  function renderHeatmap(container, payload) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const cols = buildDecadeColumns(today);

    container.innerHTML = '';
    container.classList.add('adb-act-heatmap');

    // Monatslabels — bei 10-Tages-Spalten landet jeder Monat ungefähr alle 3
    // Spalten ein neues Label. Wir setzen ein Label sobald in einem Spalten-
    // Block ein Monatswechsel passiert.
    const monthLabels = document.createElement('div');
    monthLabels.className = 'adb-act-months';
    cols.forEach((block, idx) => {
      const firstDay = block.find(d => d);
      if (!firstDay) return;
      const prev = cols[idx - 1];
      const prevLastDay = prev ? [...prev].reverse().find(d => d) : null;
      const isFirstCol = idx === 0;
      const isMonthBoundary = prevLastDay && firstDay.getMonth() !== prevLastDay.getMonth();
      if (isFirstCol || isMonthBoundary) {
        const span = document.createElement('span');
        span.className = 'adb-act-month-label';
        span.style.gridColumnStart = String(idx + 1);
        span.textContent = firstDay.toLocaleDateString('de', { month: 'short' });
        monthLabels.appendChild(span);
      }
    });
    monthLabels.style.gridTemplateColumns = `repeat(${cols.length}, 1fr)`;
    container.appendChild(monthLabels);

    const grid = document.createElement('div');
    grid.className = 'adb-act-grid';
    grid.style.gridTemplateColumns = `repeat(${cols.length}, 1fr)`;
    grid.style.gridTemplateRows    = `repeat(${ROWS_PER_COL}, 1fr)`;

    cols.forEach((block, colIdx) => {
      block.forEach((dt, rowIdx) => {
        const cell = document.createElement('span');
        cell.className = 'adb-act-cell';
        cell.style.gridColumn = String(colIdx + 1);
        cell.style.gridRow = String(rowIdx + 1);

        if (!dt) {
          cell.classList.add('adb-act-cell--empty');
          grid.appendChild(cell);
          return;
        }

        const key = fmtDate(dt);
        const entry = payload.byDay && payload.byDay[key];
        const commits = entry ? (entry.commits || 0) : 0;
        const b = bucket(commits);
        cell.classList.add('adb-act-cell--b' + b);
        cell.setAttribute('data-date', key);
        cell.setAttribute('data-commits', String(commits));
        // Commit-Zahl direkt in die Kachel schreiben (zusätzlich zur Farbe) — so sieht man
        // nicht nur die Intensität, sondern die exakte Anzahl Commits des Tages.
        if (commits > 0) {
          cell.textContent = String(commits);
          cell.classList.add('adb-act-cell--counted');
        }

        // Tooltip-Inhalt
        const kindsList = (entry && entry.kinds)
          ? Object.entries(entry.kinds).map(([k, v]) => `${k}: ${v}`).join(', ')
          : '';
        const dtFmt = dt.toLocaleDateString('de', { day: '2-digit', month: 'short', year: 'numeric' });
        const tip = commits === 0
          ? `${dtFmt} — keine Commits`
          : `${dtFmt} — ${commits} Commit${commits === 1 ? '' : 's'}${kindsList ? ` (${kindsList})` : ''}`;
        cell.title = tip;
        // Hover → Floating-Overlay mit Commits-Liste (max 8 sichtbar).
        // Klick auf die Zahl → Detail-Pane unten auf-/zuklappen (Toggle).
        if (commits > 0) {
          cell.classList.add('adb-act-cell--clickable');
          cell.addEventListener('mouseenter', (ev) => showOverlay(payload, key, ev.currentTarget));
          cell.addEventListener('mouseleave', hideOverlay);
          cell.addEventListener('click', (ev) => toggleDayDetail(payload, key, ev.currentTarget));
        }
        grid.appendChild(cell);
      });
    });

    container.appendChild(grid);

    // Legende unten rechts — 7-stufige Skala mit Schwellwert-Annotation:
    // 0 · 1–5 (grau) · 6–20 (grün) · 21+ (rot).
    const legend = document.createElement('div');
    legend.className = 'adb-act-legend';
    legend.innerHTML = `
      <span>0</span>
      <span class="adb-act-cell adb-act-cell--b0" title="keine Commits"></span>
      <span class="adb-act-cell adb-act-cell--b1" title="1–2 Commits"></span>
      <span class="adb-act-cell adb-act-cell--b2" title="3–5 Commits"></span>
      <span class="adb-act-legend__sep">5</span>
      <span class="adb-act-cell adb-act-cell--b3" title="6–12 Commits"></span>
      <span class="adb-act-cell adb-act-cell--b4" title="13–20 Commits"></span>
      <span class="adb-act-legend__sep">20</span>
      <span class="adb-act-cell adb-act-cell--b5" title="21–40 Commits"></span>
      <span class="adb-act-cell adb-act-cell--b6" title="41+ Commits"></span>
      <span>41+</span>
    `;
    container.appendChild(legend);
  }

  // ── Hover-Overlay: Floating-Tooltip mit Commit-Liste ────────────────────
  let overlayEl = null;
  function ensureOverlay() {
    if (overlayEl) return overlayEl;
    overlayEl = document.createElement('div');
    overlayEl.className = 'adb-act-overlay';
    overlayEl.setAttribute('data-show', 'false');
    document.body.appendChild(overlayEl);
    return overlayEl;
  }

  function showOverlay(payload, dateKey, anchorEl) {
    const entry = payload.byDay && payload.byDay[dateKey];
    if (!entry || !(entry.list && entry.list.length)) return;
    const el = ensureOverlay();
    const dt = new Date(dateKey + 'T00:00:00');
    const dtFmt = dt.toLocaleDateString('de', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });

    const max = 8;
    const list = entry.list.slice(0, max);
    const items = list.map(c =>
      `<li class="adb-act-overlay__item">
        <code class="adb-act-overlay__sha">${c.sha}</code>
        <span class="adb-act-overlay__kind">${c.kind}</span>
        <span>${escapeHtml(c.subject)}</span>
      </li>`
    ).join('');
    const more = entry.list.length > max ? `<div class="adb-act-overlay__more">… und ${entry.list.length - max} weitere — Klick öffnet vollständige Liste</div>` : '';

    el.innerHTML = `
      <div class="adb-act-overlay__head">
        <span class="adb-act-overlay__date">${dtFmt}</span>
        <span class="adb-act-overlay__count">${entry.commits} Commit${entry.commits === 1 ? '' : 's'}</span>
      </div>
      <ul class="adb-act-overlay__list">${items}</ul>
      ${more}
    `;

    // Positionierung: rechts neben/over der Zelle, dann clampen ans Viewport.
    const rect = anchorEl.getBoundingClientRect();
    el.setAttribute('data-show', 'true');
    // Erst zeigen, dann messen (Width ist erst nach Render bekannt)
    requestAnimationFrame(() => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      let left = rect.left + rect.width + 8;
      let top  = rect.top - 6;
      // Rechter Rand: nach links flippen
      if (left + w > window.innerWidth - 12) {
        left = rect.left - w - 8;
      }
      // Unterer Rand: nach oben verschieben
      if (top + h > window.innerHeight - 12) {
        top = Math.max(8, window.innerHeight - h - 12);
      }
      if (top < 8) top = 8;
      if (left < 8) left = 8;
      el.style.left = left + 'px';
      el.style.top  = top  + 'px';
    });
  }

  function hideOverlay() {
    if (!overlayEl) return;
    overlayEl.setAttribute('data-show', 'false');
  }

  // ── Detail-Pane: zeigt Commit-Liste fuer einen Tag oder eine Range ───────
  function ensureDetailPane() {
    let pane = document.querySelector('[data-adb-activity-detail]');
    if (!pane) {
      // Fallback: hänge unter die Heatmap an, falls Pane im MD nicht definiert.
      const host = document.querySelector('[data-adb-activity-heatmap]');
      if (!host || !host.parentNode) return null;
      pane = document.createElement('div');
      pane.setAttribute('data-adb-activity-detail', 'true');
      host.parentNode.insertBefore(pane, host.nextSibling);
    }
    pane.classList.add('adb-act-detail');
    return pane;
  }

  function renderCommitList(commits, headline) {
    if (!commits || !commits.length) {
      return `<p class="adb-act-detail__empty">Keine Commits im gewählten Zeitraum.</p>`;
    }
    const items = commits.map(c =>
      `<li class="adb-act-detail__item adb-act-detail__item--${c.kind}">
        <code class="adb-act-detail__sha">${c.sha}</code>
        <span class="adb-act-detail__kind">${c.kind}</span>
        <span class="adb-act-detail__subject">${escapeHtml(c.subject)}</span>
        ${c.date ? `<span class="adb-act-detail__date">${c.date}</span>` : ''}
      </li>`
    ).join('');
    return `
      <header class="adb-act-detail__head">
        <strong>${headline}</strong>
        <span class="adb-act-detail__count">${commits.length} Commit${commits.length === 1 ? '' : 's'}</span>
        <button type="button" class="adb-act-detail__close" aria-label="Schließen">×</button>
      </header>
      <ul class="adb-act-detail__list">${items}</ul>
    `;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Aktuell aufgeklappter Tag (oder null). Steuert das Toggle-Verhalten:
  // Klick auf dieselbe Zahl klappt den Detail-Pane wieder ein.
  let activeDetailKey = null;

  function highlightActiveCell(cellEl) {
    document.querySelectorAll('.adb-act-cell--active')
      .forEach(c => c.classList.remove('adb-act-cell--active'));
    if (cellEl) cellEl.classList.add('adb-act-cell--active');
  }

  function collapseDetail(pane) {
    if (!pane) return;
    pane.innerHTML = '';
    pane.style.display = 'none';
    activeDetailKey = null;
    highlightActiveCell(null);
  }

  // Klick auf eine Zahl-Kachel: Detail-Pane unten aufklappen; erneuter Klick
  // auf denselben Tag klappt ihn wieder ein. Klick auf einen anderen Tag
  // wechselt den Inhalt.
  function toggleDayDetail(payload, dateKey, cellEl) {
    const pane = ensureDetailPane();
    if (!pane) return;
    const isOpen = activeDetailKey === dateKey && pane.style.display !== 'none';
    if (isOpen) {
      collapseDetail(pane);
      return;
    }
    const entry = payload.byDay && payload.byDay[dateKey];
    if (!entry) return;
    const dt = new Date(dateKey + 'T00:00:00');
    const headline = dt.toLocaleDateString('de', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });
    pane.innerHTML = renderCommitList(entry.list || [], headline);
    pane.style.display = '';
    bindDetailClose(pane);
    activeDetailKey = dateKey;
    highlightActiveCell(cellEl);
    pane.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showPhaseDetail(payload, phase) {
    const pane = ensureDetailPane();
    if (!pane) return;
    const start = new Date(phase.start + 'T00:00:00');
    const end   = new Date(phase.end   + 'T23:59:59');
    const collected = [];
    Object.entries(payload.byDay || {}).forEach(([d, entry]) => {
      const dt = new Date(d + 'T12:00:00');
      if (dt >= start && dt <= end) {
        (entry.list || []).forEach(c => collected.push(Object.assign({ date: d }, c)));
      }
    });
    // Innerhalb der Phase nach Datum absteigend.
    collected.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
    pane.innerHTML = renderCommitList(collected, phase.label + ' — ' + phase.start + ' bis ' + phase.end);
    pane.style.display = '';
    bindDetailClose(pane);
    activeDetailKey = null;   // Phase-Detail ist kein Einzeltag
    highlightActiveCell(null);
    pane.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function bindDetailClose(pane) {
    const btn = pane.querySelector('.adb-act-detail__close');
    if (btn) btn.addEventListener('click', () => collapseDetail(pane));
  }

  // ── Phase-Buttons unter dem Gantt: pro Phase ein Klick-Button, der die ──
  // Range-Commits in den Detail-Pane lädt.
  function renderPhaseButtons(payload) {
    const host = document.querySelector('[data-adb-activity-phases]');
    if (!host || !payload.phases) return;
    host.innerHTML = '';
    payload.phases.forEach(p => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'adb-act-phase-btn adb-act-phase-btn--' + (p.kind || 'other');
      btn.innerHTML = `
        <span class="adb-act-phase-btn__label">${escapeHtml(p.label)}</span>
        <span class="adb-act-phase-btn__range">${p.start === p.end ? p.start : p.start + ' → ' + p.end}</span>
      `;
      btn.addEventListener('click', () => showPhaseDetail(payload, p));
      host.appendChild(btn);
    });
  }

  function renderStats(payload) {
    const target = document.querySelector('[data-adb-activity-stats]');
    if (!target || !payload.stats) return;
    const s = payload.stats;
    // Hide the `test` commit-kind pill: the real test count lives in its own
    // stat-card (s.testCount), and the commit-kind tally is misleading
    // (docs-release-sync.pattern §F).
    const top = (s.topKinds || []).filter(k => k.kind !== 'test').map(k =>
      `<span class="adb-act-pill adb-act-pill--${k.kind}">${k.kind} <em>${k.count}</em></span>`
    ).join('');
    const testsCard = (s.testCount != null)
      ? `<div><strong>${s.testCount}</strong><span>Tests</span></div>`
      : '';
    // 2-Spalten-Layout: links die drei Stat-Cards, rechts das Pills-Grid.
    // Die Klassen .adb-act-insights-grid + .adb-act-stats-grid + .adb-act-pills
    // werden in extra.css addressiert.
    target.innerHTML = `
      <div class="adb-act-insights-grid">
        <div class="adb-act-stats-grid">
          <div><strong>${s.totalCommits}</strong><span>Commits gesamt</span></div>
          <div><strong>${s.activeDays}</strong><span>aktive Tage</span></div>
          <div><strong>${s.longestStreak}</strong><span>längster Streak</span></div>
          ${testsCard}
        </div>
        <div class="adb-act-pills">${top}</div>
      </div>
    `;
  }

  async function fetchPayload() {
    const candidates = [DATA_URL, ...FALLBACK_URLS];
    for (const url of candidates) {
      try {
        const res = await fetch(url, { cache: 'no-cache' });
        if (res.ok) {
          return await res.json();
        }
      } catch (e) {
        // try next
      }
    }
    return null;
  }

  async function init() {
    const targets = document.querySelectorAll('[data-adb-activity-heatmap]');
    if (!targets.length) return;
    const payload = await fetchPayload();
    if (!payload) {
      targets.forEach(t => {
        t.innerHTML = '<em>Aktivitäts-Daten nicht gefunden — bitte <code>tools/Generate-ProjectActivity.ps1</code> ausführen.</em>';
      });
      return;
    }
    targets.forEach(t => renderHeatmap(t, payload));
    renderStats(payload);
    renderPhaseButtons(payload);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
