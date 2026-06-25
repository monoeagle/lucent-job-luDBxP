/**
 * hub-stop.js – Ende-Button für Hub-Dokumentation
 *
 * Fügt einen "Dokumentation beenden"-Button in jede Seite ein.
 * Ruft POST /api/hub-docs/stop am Hub (Port 8080) auf.
 */

(function () {
  // Hub-Port ermitteln: default 8080, überschreibbar via
  // <meta name="hub-port" content="8080"> im Theme-Hook
  const HUB_PORT = (
    document.querySelector('meta[name="hub-port"]')?.content || "8080"
  );
  const HUB_STOP_URL = `http://127.0.0.1:${HUB_PORT}/api/hub-docs/stop`;
  const HUB_URL      = `http://127.0.0.1:${HUB_PORT}`;

  function createStopBar() {
    const bar = document.createElement("div");
    bar.className = "hub-stop-bar";

    const btn = document.createElement("button");
    btn.className   = "hub-stop-btn";
    btn.textContent = "⏹ Dokumentation beenden";
    btn.title       = "Hub-Dokumentation stoppen und zurück zum Hub";

    btn.addEventListener("click", async () => {
      btn.textContent = "Wird gestoppt…";
      btn.disabled    = true;
      try {
        await fetch(HUB_STOP_URL, {
          method: "POST",
          mode:   "no-cors",   // cross-origin zum Hub
        });
      } catch (_) {
        // no-cors → kein Response-Lesen, aber Request kommt an
      }
      // Kurz warten, dann zu Hub navigieren
      setTimeout(() => {
        window.location.href = HUB_URL;
      }, 500);
    });

    bar.appendChild(btn);
    return bar;
  }

  // Einfügen nach DOM-Ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(createStopBar());
    });
  } else {
    document.body.appendChild(createStopBar());
  }
})();
