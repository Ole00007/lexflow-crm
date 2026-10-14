/* ============================================================================
 * LexFlow CRM — read-only staff Gantt view (C, Layer 1 + Layer 2)
 * static/js/gantt/gantt_view.js
 *
 * SCAFFOLD ONLY. This module fixes the CONTRACT (endpoint, whitelist, options)
 * and the page-state handling. The actual rendering function is an explicit
 * stub — it is implemented in M2/M3 once the backend endpoint exists.
 *
 * Architecture it follows (matches the rest of the Flask CRM):
 *   - server renders the page shell via Jinja (templates/gantt.html)
 *   - the JWT lives in localStorage['jwt'] (NOT in the navigation request), so
 *     this script fetches JSON client-side with `Authorization: Bearer <jwt>`,
 *     exactly like templates/tasks.html and templates/calendar.html
 *
 * Depends on: global `Gantt` from
 *   /static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js
 * ========================================================================== */
(function () {
  'use strict';

  /* ── Contract: endpoint + exact response whitelist (plan §10 Layer 1) ───── */
  var GANTT_CONFIG = {
    // Backend endpoint to be provided by the Backend agent (NOT yet built).
    // Read-only, JWT-protected, workspace-scoped server-side.
    endpoint: '/api/gantt/tasks',

    // Only these keys may appear on a task object. Anything else is a leak and
    // must fail the CT2 field-leakage cross-test.
    // Frappe Gantt consumes: id, name, start, end, progress, dependencies, custom_class
    whitelist: ['id', 'name', 'start', 'end', 'progress', 'dependencies', 'custom_class'],

    // Mount point + state containers (ids live in templates/gantt.html)
    mountId: 'gantt',
    states: ['loading', 'empty', 'error', 'denied']
  };

  /* ── Frappe Gantt 1.2.2 options for a read-only staff view ──────────────
   * Verified against src/defaults.js of the vendored 1.2.2 archive:
   *   readonly          (default false) — master switch: kills resize handles,
   *                        handle position updates and bar drag-move.
   *   readonly_dates    (default false) — blocks date edits (no resize handles,
   *                        no drag-move). Does NOT suppress the progress handle.
   *   readonly_progress (default false) — suppresses only the progress handle.
   * All three are set true so no partial code path can re-enable manipulation
   * (plan §10 Layer 1 requires readonly: true; Layer 2 forbids drag/resize/edit).
   */
  var GANTT_OPTIONS = {
    // ── read-only guarantees ──────────────────────────────────────────────
    readonly: true,
    readonly_dates: true,
    readonly_progress: true,
    move_dependencies: false,        // never re-link bars on drag (default true)

    // ── Layer 2 interaction that stays read-only ──────────────────────────
    view_mode: 'Day',
    view_mode_select: true,          // Day / Week / Month switch (default false)
    today_button: true,
    popup_on: 'click',
    infinite_padding: false,         // keep the timeline inside its scroller (375 px)

    // ── layout ────────────────────────────────────────────────────────────
    container_height: 'auto',
    bar_height: 30,
    padding: 18
  };

  /* ── Auth helper — mirrors tasks.html / calendar.html ──────────────────── */
  function token() {
    try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; }
  }

  /* ── Page-state handling (loading / empty / error / denied) ───────────── */
  function setState(name) {
    GANTT_CONFIG.states.forEach(function (s) {
      var el = document.getElementById('gantt-state-' + s);
      if (el) el.hidden = (s !== name);
    });
  }

  /* ── Fetch the read-only task payload ─────────────────────────────────── */
  function loadTasks() {
    var t = token();
    if (!t) { setState('denied'); return Promise.resolve(null); }

    setState('loading');
    return fetch(GANTT_CONFIG.endpoint, {
      headers: { 'Authorization': 'Bearer ' + t }
    })
      .then(function (res) {
        if (res.status === 401 || res.status === 403) { setState('denied'); return null; }
        if (!res.ok) { setState('error'); return null; }
        return res.json();
      })
      .then(function (payload) {
        if (!payload) return null;
        var tasks = Array.isArray(payload) ? payload : (payload.tasks || []);
        if (!tasks.length) { setState('empty'); return null; }
        return tasks;
      })
      .catch(function () { setState('error'); return null; });
  }

  /* ── Rendering — STUB (implemented in M2/M3, not now) ─────────────────────
   * When implemented this must:
   *   - drop tasks whose start/end are missing (count them, report the aggregate)
   *   - drop tasks whose end < start and warn without logging client data
   *   - map status → custom_class via docs/gantt_bar_semantics.md (canonical)
   *   - instantiate: new Gantt('#' + GANTT_CONFIG.mountId, tasks, GANTT_OPTIONS)
   *   - never issue POST/PUT/PATCH
   */
  function render(/* tasks */) {
    throw new Error('LexFlowGantt.render() not implemented — M2 scaffold only');
  }

  /* ── Public surface ───────────────────────────────────────────────────── */
  window.LexFlowGantt = {
    config: GANTT_CONFIG,
    options: GANTT_OPTIONS,
    loadTasks: loadTasks,
    render: render,
    setState: setState,
    init: function () {
      // Wire after DOM ready; rendering intentionally left to M2.
      setState('loading');
      return loadTasks().then(function (tasks) {
        if (tasks) { setState('empty'); /* TODO(M2): render(tasks) */ }
        return tasks;
      });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { window.LexFlowGantt.init(); });
  } else {
    window.LexFlowGantt.init();
  }
})();
