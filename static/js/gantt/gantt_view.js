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

  /* ── Rendering — M2 implementation ─────────────────────────────────────
   * Receives the task array from GET /api/gantt/tasks (already workspace-scoped
   * and whitelisted by the backend). This function:
   *   1. Drops tasks missing start/end (counts them)
   *   2. Drops tasks where end < start (warns, no client data in log)
   *   3. Passes custom_class through (backend already mapped status → class)
   *   4. Instantiates: new Gantt('#' + mountId, tasks, GANTT_OPTIONS)
   *   5. NEVER issues POST/PUT/PATCH — strictly read-only
   */
  function render(tasks) {
    if (!Array.isArray(tasks) || !tasks.length) { setState('empty'); return; }

    var valid = [];
    var droppedMissing = 0;
    var droppedEndBeforeStart = 0;

    for (var i = 0; i < tasks.length; i++) {
      var t = tasks[i];

      // 1. Drop tasks missing start or end
      if (!t.start || !t.end) { droppedMissing++; continue; }

      // 2. Drop tasks where end < start (warn, no client data in log)
      if (t.end < t.start) {
        droppedEndBeforeStart++;
        console.warn('LexFlowGantt: task ' + t.id + ' dropped (end < start)');
        continue;
      }

      // 3. Build the Gantt-compatible object (custom_class from backend)
      valid.push({
        id: String(t.id),
        name: t.name,
        start: t.start,
        end: t.end,
        progress: t.progress,
        dependencies: t.dependencies || '',
        custom_class: t.custom_class || ''
      });
    }

    if (droppedMissing || droppedEndBeforeStart) {
      console.info('LexFlowGantt: dropped ' + droppedMissing +
        ' missing-date, ' + droppedEndBeforeStart + ' end-before-start');
    }

    if (!valid.length) { setState('empty'); return; }

    // 4. Instantiate the read-only Gantt chart
    setState('loading');
    try {
      new Gantt('#' + GANTT_CONFIG.mountId, valid, GANTT_OPTIONS);
      // Hide loading state — the chart is rendered
      GANTT_CONFIG.states.forEach(function (s) {
        var el = document.getElementById('gantt-state-' + s);
        if (el) el.hidden = true;
      });
    } catch (e) {
      console.error('LexFlowGantt: render failed', e);
      setState('error');
    }

    // 5. NEVER issue POST/PUT/PATCH — this view is strictly read-only
  }

  /* ── Public surface ───────────────────────────────────────────────────── */
  window.LexFlowGantt = {
    config: GANTT_CONFIG,
    options: GANTT_OPTIONS,
    loadTasks: loadTasks,
    render: render,
    setState: setState,
    init: function () {
      setState('loading');
      return loadTasks().then(function (tasks) {
        if (tasks && tasks.length) { render(tasks); }
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
