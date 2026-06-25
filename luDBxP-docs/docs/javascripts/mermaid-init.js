/* ─────────────────────────────────────────────────────────────────────────
   Mermaid-Init — wandelt Zensical's `<pre class="mermaid"><code>...`
   in das von Mermaid 10+ erwartete `<div class="mermaid">...</div>`-Format
   um und initialisiert Mermaid mit Theme-passenden Settings.

   Wird nach DOMContentLoaded und nach dem Mermaid-Bundle ausgefuehrt.
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  function transformMermaidBlocks() {
    const blocks = document.querySelectorAll('pre.mermaid > code, pre.mermaid');
    const seen = new WeakSet();
    blocks.forEach((node) => {
      // `pre.mermaid > code` extrahiert den Code, `pre.mermaid` direkt
      // bekommt seinen textContent
      const pre = node.tagName === 'PRE' ? node : node.parentElement;
      if (!pre || seen.has(pre)) return;
      seen.add(pre);
      const code = pre.querySelector('code') || pre;
      const text = code.textContent.trim();
      if (!text) return;
      const div = document.createElement('div');
      div.className = 'mermaid';
      div.textContent = text;
      pre.replaceWith(div);
    });
  }

  function initMermaid() {
    if (typeof window.mermaid === 'undefined') {
      // Mermaid noch nicht geladen — kurz warten und nochmal versuchen
      setTimeout(initMermaid, 100);
      return;
    }
    transformMermaidBlocks();
    try {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: getThemeFromPalette(),
        securityLevel: 'loose',
        fontFamily: 'inherit',
      });
      window.mermaid.run({ querySelector: '.mermaid' });
    } catch (e) {
      console.error('[mermaid-init] failed:', e);
    }
  }

  function getThemeFromPalette() {
    // Material/Zensical setzt data-md-color-scheme="slate" fuer Dark-Mode
    const scheme = document.body?.getAttribute('data-md-color-scheme');
    return scheme === 'slate' ? 'dark' : 'default';
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMermaid);
  } else {
    initMermaid();
  }
})();
