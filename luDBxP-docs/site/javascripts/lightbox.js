/**
 * lightbox.js — Minimaler Bild-Lightbox fuer die Doku.
 *
 * Was es macht:
 *  - Sucht alle <img> im Hauptinhalt und macht sie klickbar (cursor: zoom-in).
 *  - Klick oeffnet ein Overlay mit dem Bild in voller Groesse + dunklem
 *    Backdrop. Bilder werden auf maximal 95vw / 88vh skaliert.
 *  - Vor/Zurueck durch ALLE Bilder der aktuellen Seite via Pfeiltasten oder
 *    Buttons am Rand. Wrap-around in beide Richtungen.
 *  - Counter "3 / 8" rechts oben (nur wenn > 1 Bild).
 *  - Schliessen: ESC, Klick auf Backdrop, Klick auf X-Button.
 *  - Alt-Text wird als Caption unter dem Bild angezeigt.
 *
 * Hinweis zu Mermaid-Diagrammen: seit dem Pre-Render-Umbau (tools/MermaidRenderer)
 * werden alle Mermaid-Diagramme bereits beim docs:build zu .svg gerendert und
 * via <img src=".../*.svg"> referenziert — das normale Bild-Binding deckt sie
 * also automatisch mit ab. Eine Mermaid-Sonderbehandlung gibt es daher hier
 * NICHT mehr.
 *
 * Was es NICHT macht:
 *  - Keine externen Dependencies (keine CDN, kein jQuery, kein Build-Step).
 *  - Kein Swipe/Zoom-Gestures — Pfeiltasten + Buttons reichen fuer Doku.
 *  - Keine Theme-Variante: ein universeller dunkler Backdrop, der in Hell-
 *    und Dunkelmodus gleichermassen funktioniert.
 *
 * Heuristik fuer "doku-relevante Bilder":
 *  - <img>-Tags innerhalb von .md-content article, naturalWidth > 100px
 *    (filtert Inline-Emoji-Icons, Badges)
 *  - Kein .no-lightbox-CSS-Class (Opt-out per Markdown wenn noetig)
 */
(function () {
  'use strict';

  var OVERLAY_ID = 'adb-lightbox-overlay';
  var MIN_WIDTH = 100;

  var mediaList = [];
  var currentIndex = -1;

  function buildOverlay() {
    if (document.getElementById(OVERLAY_ID)) return;
    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.className = 'adb-lightbox-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<button class="adb-lightbox-close" aria-label="Schliessen">&times;</button>' +
      '<button class="adb-lightbox-nav adb-lightbox-prev" aria-label="Vorheriges Bild">&#10094;</button>' +
      '<button class="adb-lightbox-nav adb-lightbox-next" aria-label="Naechstes Bild">&#10095;</button>' +
      '<div class="adb-lightbox-counter"></div>' +
      '<div class="adb-lightbox-content"></div>' +
      '<div class="adb-lightbox-caption"></div>';
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target.classList.contains('adb-lightbox-close')) {
        closeLightbox();
      }
    });

    overlay.querySelector('.adb-lightbox-prev').addEventListener('click', function (e) {
      e.stopPropagation();
      navigate(-1);
    });
    overlay.querySelector('.adb-lightbox-next').addEventListener('click', function (e) {
      e.stopPropagation();
      navigate(1);
    });
  }

  function getScope() {
    return document.querySelector('.md-content article')
        || document.querySelector('.md-content')
        || document.body;
  }

  function getDocMedia() {
    var scope = getScope();
    var out = [];
    scope.querySelectorAll('img').forEach(function (el) {
      if (el.classList.contains('no-lightbox')) return;
      if (el.dataset.adbLightboxBound !== '1') return;
      out.push({ src: el.currentSrc || el.src, caption: el.alt || '' });
    });
    return out;
  }

  function showAt(idx) {
    if (idx < 0 || idx >= mediaList.length) return;
    var item = mediaList[idx];
    var overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    var content = overlay.querySelector('.adb-lightbox-content');
    var cap     = overlay.querySelector('.adb-lightbox-caption');
    var cnt     = overlay.querySelector('.adb-lightbox-counter');
    var prev    = overlay.querySelector('.adb-lightbox-prev');
    var next    = overlay.querySelector('.adb-lightbox-next');

    content.innerHTML = '';
    var img = document.createElement('img');
    img.className = 'adb-lightbox-img';
    img.src = item.src;
    img.alt = item.caption || '';
    content.appendChild(img);

    cap.textContent = item.caption || '';
    cap.style.display = item.caption ? 'block' : 'none';

    var multi = mediaList.length > 1;
    prev.style.display = multi ? 'flex' : 'none';
    next.style.display = multi ? 'flex' : 'none';
    cnt.style.display  = multi ? 'block' : 'none';
    if (multi) {
      cnt.textContent = (idx + 1) + ' / ' + mediaList.length;
    }
    currentIndex = idx;
  }

  function navigate(delta) {
    if (mediaList.length === 0) return;
    var n = mediaList.length;
    var next = ((currentIndex + delta) % n + n) % n;
    showAt(next);
  }

  function openLightboxFor(element) {
    mediaList = getDocMedia();
    var idx = -1;
    var src = element.currentSrc || element.src;
    for (var i = 0; i < mediaList.length; i++) {
      if (mediaList[i].src === src) { idx = i; break; }
    }
    if (idx < 0) return;
    var overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.add('open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    showAt(idx);
  }

  function closeLightbox() {
    var overlay = document.getElementById(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.remove('open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    overlay.querySelector('.adb-lightbox-content').innerHTML = '';
    currentIndex = -1;
  }

  function attachToImages() {
    var scope = getScope();
    scope.querySelectorAll('img').forEach(function (img) {
      if (img.classList.contains('no-lightbox')) return;
      if (img.dataset.adbLightboxBound === '1') return;
      function bind() {
        // Akzeptiere naturalWidth (Raster) ODER gerenderte Breite (SVG mit
        // width="100%" hat haeufig naturalWidth=0 in Chrome/Firefox).
        var rect = img.getBoundingClientRect();
        var renderW = rect.width;
        if (img.naturalWidth < MIN_WIDTH && renderW < MIN_WIDTH) return;
        img.style.cursor = 'zoom-in';
        img.dataset.adbLightboxBound = '1';
        img.addEventListener('click', function (e) {
          e.preventDefault();
          openLightboxFor(img);
        });
      }
      if (img.complete) {
        bind();
      } else {
        img.addEventListener('load', bind, { once: true });
      }
    });
  }

  function init() {
    buildOverlay();
    attachToImages();
    document.addEventListener('keydown', function (e) {
      var overlay = document.getElementById(OVERLAY_ID);
      if (!overlay || !overlay.classList.contains('open')) return;
      if (e.key === 'Escape')          { closeLightbox(); e.preventDefault(); }
      else if (e.key === 'ArrowLeft')  { navigate(-1);   e.preventDefault(); }
      else if (e.key === 'ArrowRight') { navigate(1);    e.preventDefault(); }
    });
    // Material-Theme tauscht Hauptinhalt bei Navigation per JS aus —
    // re-bind via MutationObserver.
    var content = document.querySelector('.md-container') || document.body;
    if ('MutationObserver' in window) {
      var mo = new MutationObserver(function () { attachToImages(); });
      mo.observe(content, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
