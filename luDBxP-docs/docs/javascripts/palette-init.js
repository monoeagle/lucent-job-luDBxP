/**
 * palette-init.js — Zensical-Workaround fuer den Hell/Dunkel-Palette-Toggle.
 *
 * Hintergrund:
 * Zensical (in der Version 0.0.41) emittiert die zwei Palette-`<label>`-Toggles
 * mit `hidden`-Attribut auf BEIDEN und ohne `checked` auf den Radio-Inputs. Das
 * MkDocs-Material-Bundle erwartet aber einen aktiven Input + ein-sichtbares-
 * Label und un-hided dann gar nichts → der Toggle ist nie sichtbar.
 *
 * Dieser Loader holt das nach:
 *  1. Aktive Color-Scheme aus localStorage (__palette.color.scheme) oder ueber
 *     `matchMedia('(prefers-color-scheme: dark)')` raten.
 *  2. Den passenden Radio anhaken + das passende Label sichtbar machen (das ist
 *     IMMER das Label, das auf den ANDEREN Modus umschaltet → naemlich die
 *     `for="<andere-id>"`-Variante).
 *  3. Bei Klick: localStorage updaten + Visibility nachfuehren (sonst kann
 *     Material nach Reload nicht erkennen, welches Schema aktiv war).
 */
(function () {
  'use strict';

  function readStoredScheme() {
    try {
      var raw = localStorage.getItem('__palette');
      if (!raw) return null;
      var obj = JSON.parse(raw);
      return obj && obj.color ? obj.color.scheme : null;
    } catch (e) { return null; }
  }

  function writeScheme(scheme, media, primary, accent) {
    try {
      localStorage.setItem('__palette', JSON.stringify({
        index: scheme === 'slate' ? 1 : 0,
        color: { scheme: scheme, media: media, primary: primary, accent: accent }
      }));
    } catch (e) { /* private mode etc. — ignore */ }
  }

  function syncBody(input) {
    document.body.setAttribute('data-md-color-scheme', input.getAttribute('data-md-color-scheme'));
    document.body.setAttribute('data-md-color-primary', input.getAttribute('data-md-color-primary'));
    document.body.setAttribute('data-md-color-accent',  input.getAttribute('data-md-color-accent'));
  }

  function syncVisibility(activeInput, allInputs) {
    // Sichtbarkeits-Logik: Das Label, dessen for="..." auf den AKTIVEN Input
    // zeigt, gehoert zum AKTIVEN Modus und ist immer hidden (man kann nicht von
    // hell zu hell wechseln). Das Label, das auf den INAKTIVEN Input zeigt,
    // muss sichtbar sein — das ist der Klickbare-Toggle.
    var activeId = activeInput.id;
    allInputs.forEach(function (inp) {
      var label = document.querySelector('label[for="' + inp.id + '"]');
      if (!label) return;
      if (inp.id === activeId) {
        // for=<active> → klickt zum aktiven Schema → kein sichtbarer Toggle.
        label.setAttribute('hidden', '');
      } else {
        // for=<inaktiv> → klickt zum anderen Schema → sichtbar.
        label.removeAttribute('hidden');
      }
    });
  }

  function init() {
    var form = document.querySelector('form[data-md-component="palette"]');
    if (!form) return;
    var inputs = Array.prototype.slice.call(form.querySelectorAll('input.md-option[type="radio"]'));
    if (inputs.length < 2) return;

    // Schema-Wahl: zuerst localStorage, dann prefers-color-scheme.
    var stored = readStoredScheme();
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var targetScheme = stored || (prefersDark ? 'slate' : 'default');

    var active = inputs.filter(function (i) {
      return i.getAttribute('data-md-color-scheme') === targetScheme;
    })[0] || inputs[0];

    active.checked = true;
    syncBody(active);
    syncVisibility(active, inputs);

    // Bei Klick auf einen Toggle-Label: Visibility neu setzen + localStorage.
    inputs.forEach(function (inp) {
      inp.addEventListener('change', function () {
        if (!inp.checked) return;
        syncBody(inp);
        syncVisibility(inp, inputs);
        writeScheme(
          inp.getAttribute('data-md-color-scheme'),
          inp.getAttribute('data-md-color-media'),
          inp.getAttribute('data-md-color-primary'),
          inp.getAttribute('data-md-color-accent')
        );
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
