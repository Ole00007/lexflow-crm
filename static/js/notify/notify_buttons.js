/* LexFlow — Telegram / WhatsApp notification buttons (WS-C).
 *
 * Deep-link first: the server builds the links (/api/notify/task/<id>/links);
 * this script just fetches them and opens them in a new tab.
 *
 * Security:
 *   - JWT read from localStorage['jwt'] (same pattern as gantt_view.js).
 *   - Links opened with rel=noopener (window.open 'noopener').
 *   - NEVER uses innerHTML with data — only textContent / createElement.
 */
(function () {
  "use strict";

  function jwt() {
    try { return localStorage.getItem("jwt") || ""; } catch (e) { return ""; }
  }

  function fetchLinks(taskId) {
    return fetch("/api/notify/task/" + encodeURIComponent(taskId) + "/links", {
      headers: { "Authorization": "Bearer " + jwt() }
    }).then(function (r) {
      if (!r.ok) { throw new Error("notify links HTTP " + r.status); }
      return r.json();
    });
  }

  function openUrl(url) {
    if (!url) { return; }
    var w = window.open(url, "_blank", "noopener,noreferrer");
    if (w) { try { w.opener = null; } catch (e) { /* noop */ } }
  }

  function openTelegram(task) {
    fetchLinks(task.id).then(function (data) {
      var tg = (data && data.telegram) || {};
      openUrl(tg.deeplink || tg.share);
    }).catch(function () { /* silent — no sensitive detail in UI */ });
  }

  function openWhatsApp(task) {
    fetchLinks(task.id).then(function (data) {
      var wa = (data && data.whatsapp) || {};
      openUrl(wa.link);
    }).catch(function () { /* silent */ });
  }

  // ── Gantt integration (optional; only when the Gantt exposes its API) ──
  if (window.LexFlowGantt && typeof window.LexFlowGantt.registerAction === "function") {
    window.LexFlowGantt.registerAction({
      label: "Telegram",
      when: function (task) { return !!(task && task.id); },
      onClick: function (task) { openTelegram(task); }
    });
    window.LexFlowGantt.registerAction({
      label: "WhatsApp",
      when: function (task) { return !!(task && task.id); },
      onClick: function (task) { openWhatsApp(task); }
    });
  }

  // ── Standalone helper for case / task pages ──
  function makeButton(label, cssClass, onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "notify-btn " + cssClass;
    b.textContent = label;                 // textContent — never innerHTML
    b.setAttribute("aria-label", label + " notification");
    b.addEventListener("click", function (e) {
      e.preventDefault();
      onClick();
    });
    return b;
  }

  /**
   * Return [telegramButton, whatsappButton] for a given task id.
   * Callers append these where they like (case page, task row, etc.).
   */
  function buttonsFor(taskId) {
    var tgl = makeButton("Telegram", "notify-btn-telegram", function () {
      openTelegram({ id: taskId });
    });
    var wab = makeButton("WhatsApp", "notify-btn-whatsapp", function () {
      openWhatsApp({ id: taskId });
    });
    return [tgl, wab];
  }

  window.LexFlowNotify = {
    buttonsFor: buttonsFor,
    fetchLinks: fetchLinks
  };
})();
