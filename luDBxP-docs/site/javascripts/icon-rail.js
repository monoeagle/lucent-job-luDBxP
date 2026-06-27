/* ───────────────────────────────────────────────────────────────────────────
   Icon-Rail + Flyout-Panel — für LucentTools DB Explorer adaptiert (2026-06-25).

   Basis: .pattern/prereqs/docs/icon-rail.js (neutrale Vorlage).
   Portiert aus: adb-control-docs → libredrive-docs → luDBxP-docs.

   ADAPT-Marker gesetzt:
   - APP_VERSION, HEADER_PREFIX, LS_KEY, isHomePage-Regex
   - INFO_HTML Stack (Python/Flask/SQLAlchemy/NetworkX/Cytoscape.js)
   - Status-Badge (v0.1.0, 81 Tests)
   - addRoadmapBadge entfernt (kein Gantt-SVG in v0.1.0)
   ─────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // ── Versionen ──────────────────────────────────────────────────────────
  const APP_VERSION   = '0.25.0';                       // ADAPT: bei Release anpassen
  const TEST_COUNT    = '194';                          // ADAPT: bei Release anpassen
  const TEST_DATE     = '2026-06-27';                   // ADAPT: bei Release anpassen
  const HEADER_PREFIX = `LucentTools DB Explorer v${APP_VERSION}`;

  // ── Icon-Map: Titel-Schluesselwort → Emoji ─────────────────────────────
  const ICON_MAP = [
    { match: ['überblick', 'uberblick', 'start', 'home', 'overview'], icon: '🏠' },
    { match: ['grundlagen', 'basics', 'getting-started'], icon: '📚' },
    { match: ['referenz', 'reference', 'api', 'cli'],     icon: '📖' },
    { match: ['entwicklung', 'development'],              icon: '🔧' },
    { match: ['projekt', 'project'],                      icon: '🗺' },
    { match: ['changelog', 'änderungen', 'aenderungen'],  icon: '📜' },
    { match: ['arbeitspakete', 'todo', 'aufgaben'],       icon: '📋' },
    { match: ['architektur', 'architecture'],             icon: '🏛' },
    { match: ['audit'],                                   icon: '📊' },
  ];
  const ICON_FALLBACK = '📄';

  function pickIcon(title) {
    const t = (title || '').toLowerCase();
    for (const entry of ICON_MAP) {
      if (entry.match.some(kw => t.includes(kw))) return entry.icon;
    }
    return ICON_FALLBACK;
  }

  // ── Parse: Material primary-nav → Tree-Modell (rekursiv) ──────────────
  function extractTitle(li) {
    const span = li.querySelector(':scope > a > .md-ellipsis, :scope > label > .md-ellipsis');
    if (span) return span.textContent.trim();
    const lbl = li.querySelector(':scope > label.md-nav__link');
    if (lbl) return lbl.textContent.trim();
    return '';
  }

  function parseList(ul) {
    const items = [];
    const lis = Array.from(ul.children).filter(el => el.matches('li.md-nav__item'));
    for (const li of lis) {
      const directLink = li.querySelector(':scope > a.md-nav__link');
      const subnav = li.querySelector(':scope > nav.md-nav');
      const title = extractTitle(li);

      if (subnav) {
        const subList = subnav.querySelector(':scope > ul.md-nav__list');
        const children = subList ? parseList(subList) : [];
        items.push({ type: 'group', title, children });
      } else if (directLink) {
        items.push({
          type: 'page',
          title,
          href: directLink.getAttribute('href'),
          active: directLink.classList.contains('md-nav__link--active'),
        });
      }
    }
    return items;
  }

  function parseSections() {
    const primary = document.querySelector('nav.md-nav--primary > ul.md-nav__list');
    if (!primary) return [];

    const sections = [];
    const topItems = Array.from(primary.children).filter(el => el.matches('li.md-nav__item'));

    for (const li of topItems) {
      const directLink = li.querySelector(':scope > a.md-nav__link');
      const subnav = li.querySelector(':scope > nav.md-nav');
      const title = extractTitle(li);

      let tree = [];
      if (subnav) {
        const subList = subnav.querySelector(':scope > ul.md-nav__list');
        if (subList) tree = parseList(subList);
      }

      sections.push({
        title,
        href: directLink ? directLink.getAttribute('href') : null,
        tree,
        active: li.classList.contains('md-nav__item--active'),
        icon: pickIcon(title),
      });
    }

    return sections;
  }

  // ── Build: Icon-Rail + Flyout im DOM ───────────────────────────────────
  function buildRail(sections) {
    const rail = document.createElement('aside');
    rail.className = 'adb-rail';
    rail.setAttribute('aria-label', 'Sektions-Navigation');

    const flyout = document.createElement('div');
    flyout.className = 'adb-rail-flyout';
    flyout.setAttribute('aria-hidden', 'true');

    sections.forEach((sec, idx) => {
      const btn = document.createElement('button');
      btn.className = 'adb-rail-btn';
      btn.type = 'button';
      btn.dataset.sectionIdx = String(idx);
      btn.setAttribute('aria-label', sec.title);
      btn.title = sec.title;
      if (sec.active) btn.classList.add('adb-rail-btn--active');

      btn.innerHTML = `<span class="adb-rail-icon">${sec.icon}</span>`;
      rail.appendChild(btn);

      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (sec.href && sec.tree.length === 0) {
          persistIdx(-1);
          window.location.href = sec.href;
          return;
        }
        openFlyout(idx);
      });
    });

    document.body.appendChild(rail);
    document.body.appendChild(flyout);
    return { rail, flyout };
  }

  // ── Flyout-State (persistent via localStorage) ─────────────────────────
  const LS_KEY = 'ludbxp-rail.flyoutIdx';  // ADAPT: eindeutiger Key je Projekt
  const INFO_IDX = -2;
  let _currentIdx = -1;
  let _sections = [];

  function persistIdx(idx) {
    try { localStorage.setItem(LS_KEY, String(idx)); } catch (_) {}
  }

  function loadPersistedIdx() {
    try {
      const v = localStorage.getItem(LS_KEY);
      const n = v == null ? -1 : parseInt(v, 10);
      return Number.isFinite(n) ? n : -1;
    } catch (_) { return -1; }
  }

  function renderSectionFlyout(sec) {
    return (
      '<header class="adb-rail-flyout__head">' +
        '<span class="adb-rail-flyout__icon">' + sec.icon + '</span>' +
        '<span class="adb-rail-flyout__title">' + escapeHtml(sec.title) + '</span>' +
      '</header>' +
      '<ul class="adb-rail-flyout__list">' + renderTree(sec.tree, 0) + '</ul>' +
      '<button class="adb-rail-flyout__toggle" type="button" aria-label="Sidebar einklappen" title="Einklappen">◀</button>'
    );
  }

  function bindFlyoutHandlers(flyout) {
    const toggle = flyout.querySelector('.adb-rail-flyout__toggle');
    if (toggle) toggle.addEventListener('click', closeFlyout);
    flyout.querySelectorAll('.adb-rail-flyout__groupbtn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const group = btn.closest('.adb-rail-flyout__group');
        if (group) group.classList.toggle('adb-rail-flyout__group--closed');
      });
    });
  }

  function openFlyout(idx) {
    const flyout = document.querySelector('.adb-rail-flyout');
    const rail   = document.querySelector('.adb-rail');
    if (!flyout || !rail) return;

    const sec = _sections[idx];
    if (!sec) return;

    if (_currentIdx === idx && flyout.classList.contains('adb-rail-flyout--open')) {
      closeFlyout();
      return;
    }

    const isAlreadyOpen = flyout.classList.contains('adb-rail-flyout--open');
    const isSwitch = isAlreadyOpen && _currentIdx !== idx && _currentIdx !== -1;

    _currentIdx = idx;
    persistIdx(idx);

    rail.querySelectorAll('.adb-rail-btn').forEach(b => b.classList.remove('adb-rail-btn--current'));
    const btn = rail.querySelector(`.adb-rail-btn[data-section-idx="${idx}"]`);
    if (btn) btn.classList.add('adb-rail-btn--current');

    const html = renderSectionFlyout(sec);

    if (isSwitch) {
      flyout.classList.add('adb-rail-flyout--fading');
      setTimeout(() => {
        flyout.innerHTML = html;
        bindFlyoutHandlers(flyout);
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            flyout.classList.remove('adb-rail-flyout--fading');
          });
        });
      }, 110);
    } else {
      flyout.innerHTML = html;
      bindFlyoutHandlers(flyout);
      flyout.classList.add('adb-rail-flyout--open');
      flyout.setAttribute('aria-hidden', 'false');
    }
  }

  // ── Tree-Render (rekursiv) ────────────────────────────────────────────
  function renderTree(items, depth) {
    return items.map(item => {
      if (item.type === 'page') {
        return (
          '<li class="adb-rail-flyout__item' + (item.active ? ' adb-rail-flyout__item--active' : '') +
          '" data-depth="' + depth + '">' +
            '<a href="' + item.href + '">' + escapeHtml(item.title) + '</a>' +
          '</li>'
        );
      }
      return (
        '<li class="adb-rail-flyout__group" data-depth="' + depth + '">' +
          '<button class="adb-rail-flyout__groupbtn" type="button">' +
            '<span class="adb-rail-flyout__chev">▾</span>' +
            '<span class="adb-rail-flyout__grouplabel">' + escapeHtml(item.title) + '</span>' +
          '</button>' +
          '<ul class="adb-rail-flyout__sublist">' +
            renderTree(item.children, depth + 1) +
          '</ul>' +
        '</li>'
      );
    }).join('');
  }

  // ── Info-Flyout (Entwickler + Stack) ──────────────────────────────────
  const INFO_HTML =
    '<header class="adb-rail-flyout__head">' +
      '<span class="adb-rail-flyout__icon">ℹ</span>' +
      '<span class="adb-rail-flyout__title">Über</span>' +
    '</header>' +
    '<div class="adb-rail-flyout__info">' +
      '<section class="adb-info-block">' +
        '<h4>Entwickler</h4>' +
        '<p><strong>Tobias Philipp</strong> / LucentTools<br>' +
        '<a href="https://github.com/monoeagle" target="_blank" rel="noopener">github.com/monoeagle</a></p>' +
      '</section>' +
      '<section class="adb-info-block">' +
        '<h4>Stack</h4>' +
        '<table class="adb-info-stack">' +
          '<tr><td>LucentTools DB Explorer</td><td>v' + APP_VERSION + '</td></tr>' +
          '<tr><td>Python</td><td>3.x</td></tr>' +
          '<tr><td>Flask</td><td>≥ 3.0</td></tr>' +
          '<tr><td>SQLAlchemy</td><td>≥ 2.0</td></tr>' +
          '<tr><td>NetworkX</td><td>≥ 3.0</td></tr>' +
          '<tr><td>Cytoscape.js</td><td>3.30.2</td></tr>' +
          '<tr><td>pytest</td><td>' + TEST_COUNT + ' Tests</td></tr>' +
          '<tr><td>Mermaid</td><td>11.x</td></tr>' +
          '<tr><td>Zensical</td><td>Docs</td></tr>' +
        '</table>' +
      '</section>' +
    '</div>' +
    '<button class="adb-rail-flyout__toggle" type="button" aria-label="Einklappen" title="Einklappen">◀</button>';

  function openInfoFlyout() {
    const flyout = document.querySelector('.adb-rail-flyout');
    const rail   = document.querySelector('.adb-rail');
    if (!flyout || !rail) return;

    if (_currentIdx === INFO_IDX && flyout.classList.contains('adb-rail-flyout--open')) {
      closeFlyout();
      return;
    }
    _currentIdx = INFO_IDX;
    persistIdx(INFO_IDX);

    rail.querySelectorAll('.adb-rail-btn--current').forEach(b => b.classList.remove('adb-rail-btn--current'));
    const infoBtn = rail.querySelector('.adb-rail-btn--info');
    if (infoBtn) infoBtn.classList.add('adb-rail-btn--current');

    flyout.innerHTML = INFO_HTML;
    flyout.classList.add('adb-rail-flyout--open');
    flyout.setAttribute('aria-hidden', 'false');
    flyout.querySelector('.adb-rail-flyout__toggle').addEventListener('click', closeFlyout);
  }

  function closeFlyout() {
    const flyout = document.querySelector('.adb-rail-flyout');
    const rail   = document.querySelector('.adb-rail');
    if (flyout) {
      flyout.classList.remove('adb-rail-flyout--open');
      flyout.setAttribute('aria-hidden', 'true');
    }
    if (rail) {
      rail.querySelectorAll('.adb-rail-btn--current').forEach(b => b.classList.remove('adb-rail-btn--current'));
    }
    _currentIdx = -1;
    persistIdx(-1);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    const lightboxOpen = document.querySelector('.adb-lightbox-overlay.open');
    if (lightboxOpen) return;
    closeFlyout();
  });

  function escapeHtml(s) {
    return (s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Header-Title-Override ─────────────────────────────────────────────
  function updateHeaderTitle() {
    const firstTopic = document.querySelector(
      '.md-header__title .md-header__topic:not([data-md-component]) .md-ellipsis'
    );
    if (!firstTopic) return;

    const h1 = document.querySelector('.md-content__inner h1, article h1');
    let pageTitle = '';
    if (h1) {
      pageTitle = h1.textContent.replace(/[¶#]\s*$/, '').trim();
    }

    // Startseite: H1 enthält "LucentTools DB Explorer" → nur Prefix ohne Doppelnennung
    const isHomePage = /lucent db explorer|ludbxp/i.test(pageTitle);  // ADAPT

    if (!pageTitle || isHomePage) {
      firstTopic.textContent = HEADER_PREFIX;
    } else {
      firstTopic.textContent = `${HEADER_PREFIX}: ${pageTitle}`;
    }
  }

  // ── Rail-Footer: Info + Palette-Toggle ─────────────────────────────────
  function getCurrentScheme() {
    return (
      document.body.dataset.mdColorScheme ||
      document.documentElement.dataset.mdColorScheme ||
      ''
    );
  }

  function paletteIconFor(scheme) {
    return scheme === 'slate' ? '☀️' : '🌙';
  }

  function togglePalette() {
    const isDark = getCurrentScheme() === 'slate';
    const target = document.getElementById(isDark ? '__palette_0' : '__palette_1');
    if (!target) return;
    target.checked = true;
    target.dispatchEvent(new Event('change', { bubbles: true }));
    setTimeout(() => {
      const ico = document.getElementById('adb-palette-icon');
      if (ico) ico.textContent = paletteIconFor(getCurrentScheme());
    }, 60);
  }

  function addRailFooter() {
    const rail = document.querySelector('.adb-rail');
    if (!rail) return;

    const footer = document.createElement('div');
    footer.className = 'adb-rail-footer';

    const infoBtn = document.createElement('button');
    infoBtn.type = 'button';
    infoBtn.className = 'adb-rail-btn adb-rail-btn--util adb-rail-btn--info';
    infoBtn.title = `Über ${HEADER_PREFIX} — Entwickler · Stack`;
    infoBtn.setAttribute('aria-label', 'Über');
    infoBtn.innerHTML = '<span class="adb-rail-icon">ℹ</span>';
    infoBtn.addEventListener('click', openInfoFlyout);
    footer.appendChild(infoBtn);

    const paletteBtn = document.createElement('button');
    paletteBtn.type = 'button';
    paletteBtn.className = 'adb-rail-btn adb-rail-btn--util';
    paletteBtn.title = 'Hell-/Dunkelmodus umschalten';
    paletteBtn.setAttribute('aria-label', 'Palette umschalten');
    paletteBtn.innerHTML = `<span class="adb-rail-icon" id="adb-palette-icon">${paletteIconFor(getCurrentScheme())}</span>`;
    paletteBtn.addEventListener('click', togglePalette);
    footer.appendChild(paletteBtn);

    rail.appendChild(footer);
  }

  // ── Roadmap-Badge im Header → Gantt im Modal ──────────────────────────
  function roadmapSvgUrl() {
    const s = document.querySelector('script[src*="javascripts/icon-rail.js"]');
    const base = s ? s.src.replace(/javascripts\/icon-rail\.js.*$/, '') : '/';
    return base + 'images/mermaid/projekt-roadmap-1.svg';
  }
  function closeRoadmap() {
    const ov = document.getElementById('adb-roadmap-overlay');
    if (!ov) return;
    ov.classList.remove('open');
    ov.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }
  function openRoadmap() {
    let ov = document.getElementById('adb-roadmap-overlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'adb-roadmap-overlay';
      ov.className = 'adb-lightbox-overlay';
      ov.setAttribute('role', 'dialog');
      ov.setAttribute('aria-modal', 'true');
      ov.innerHTML =
        '<button class="adb-lightbox-close" aria-label="Schliessen">&times;</button>' +
        '<div class="adb-lightbox-content"><img class="adb-lightbox-img" src="' +
        roadmapSvgUrl() + '" alt="Arbeitspaket-Roadmap (Gantt)"></div>' +
        '<div class="adb-lightbox-caption">Arbeitspaket-Roadmap (Gantt)</div>';
      document.body.appendChild(ov);
      ov.addEventListener('click', function (e) {
        if (e.target === ov || e.target.classList.contains('adb-lightbox-close')) {
          closeRoadmap();
        }
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && ov.classList.contains('open')) closeRoadmap();
      });
    }
    ov.classList.add('open');
    ov.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  // ── Architektur-Badge im Header → Architekturbild im Modal ────────────
  function archSvgUrl() {
    const s = document.querySelector('script[src*="javascripts/icon-rail.js"]');
    const base = s ? s.src.replace(/javascripts\/icon-rail\.js.*$/, '') : '/';
    return base + 'images/mermaid/referenz-architektur-3.svg';
  }
  function closeArch() {
    const ov = document.getElementById('adb-arch-overlay');
    if (!ov) return;
    ov.classList.remove('open');
    ov.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }
  function openArch() {
    let ov = document.getElementById('adb-arch-overlay');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'adb-arch-overlay';
      ov.className = 'adb-lightbox-overlay';
      ov.setAttribute('role', 'dialog');
      ov.setAttribute('aria-modal', 'true');
      ov.innerHTML =
        '<button class="adb-lightbox-close" aria-label="Schliessen">&times;</button>' +
        '<div class="adb-lightbox-content"><img class="adb-lightbox-img" src="' +
        archSvgUrl() + '" alt="Systemüberblick: UI · Flask-API · Core-Layer"></div>' +
        '<div class="adb-lightbox-caption">Architektur — UI · Flask-API · Core-Layer</div>';
      document.body.appendChild(ov);
      ov.addEventListener('click', function (e) {
        if (e.target === ov || e.target.classList.contains('adb-lightbox-close')) {
          closeArch();
        }
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && ov.classList.contains('open')) closeArch();
      });
    }
    ov.classList.add('open');
    ov.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }
  function addArchBadge() {
    const search = document.querySelector('.md-search');
    if (!search || !search.parentNode) return;
    if (document.querySelector('.adb-arch-badge')) return;  // idempotent
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'adb-status-badge adb-arch-badge';
    btn.title = 'Architekturbild (Systemüberblick) öffnen';
    btn.innerHTML =
      '<span class="adb-status-badge__dot" aria-hidden="true"></span>Architektur';
    btn.addEventListener('click', openArch);
    search.parentNode.insertBefore(btn, search);
  }

  function addRoadmapBadge() {
    const search = document.querySelector('.md-search');
    if (!search || !search.parentNode) return;
    if (document.querySelector('.adb-roadmap-badge')) return;  // idempotent
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'adb-status-badge adb-roadmap-badge';
    btn.title = 'Arbeitspaket-Roadmap (Gantt) öffnen';
    btn.innerHTML =
      '<span class="adb-status-badge__dot" aria-hidden="true"></span>Roadmap';
    btn.addEventListener('click', openRoadmap);
    search.parentNode.insertBefore(btn, search);
  }

  // ── Status-Badge im Header ────────────────────────────────────────────
  function addStatusBadge() {
    const search = document.querySelector('.md-search');
    if (!search || !search.parentNode) return;
    if (document.querySelector('.adb-status-badge')) return;
    const badge = document.createElement('span');
    badge.className = 'adb-status-badge';
    badge.title = `LucentTools DB Explorer v${APP_VERSION} — ${TEST_COUNT} Tests grün (pytest, Stand ${TEST_DATE}). ` +
      'SQLite/PostgreSQL/MySQL/MSSQL via SQLAlchemy. FK-Graph (NetworkX), Join-Pfad-Builder (k-kürzeste Pfade), ' +
      'Cytoscape.js-Graph-Visualisierung, Implizite-FK-Heuristik, Datenvorschau, Verbindungs-Manager. ' +
      'Demo-CMDB deckt Diamant-Pfade, zusammengesetzte FKs, isolierte Tabellen, Selbstreferenzen ab.';
    badge.innerHTML = '<span class="adb-status-badge__dot" aria-hidden="true"></span>v' + APP_VERSION + ' · ' + TEST_COUNT + ' Tests';
    search.parentNode.insertBefore(badge, search);
  }

  // ── Init ───────────────────────────────────────────────────────────────
  function init() {
    updateHeaderTitle();
    addStatusBadge();
    addArchBadge();
    addRoadmapBadge();

    const sections = parseSections();
    if (sections.length === 0) return;
    _sections = sections;
    buildRail(sections);
    addRailFooter();

    const persisted = loadPersistedIdx();
    if (persisted === INFO_IDX) {
      openInfoFlyout();
    } else if (persisted >= 0 && persisted < sections.length && sections[persisted].tree.length > 0) {
      openFlyout(persisted);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
