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

  /* ── Team, docs & agent actions (WS-A) ─────────────────────────────────── */
  var ROLE_TAG = { case_owner: 'Owner', docs_supply: 'Docs', legal_assistant: 'Assist', lawyer_review: 'Lawyer' };
  var actionRegistry = [];   // other modules (Telegram / WhatsApp buttons…) plug popup buttons in here

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function shortName(n) {            // "Elena Romanelli" -> "E.Romanelli"; "Elisa" -> "Elisa"
    var p = String(n || '').trim().split(/\s+/);
    return p.length > 1 ? p[0].charAt(0) + '.' + p[p.length - 1] : (p[0] || '?');
  }

  // Fixed-height scroller = the month/week header (sticky) stays glued above the bars
  function chartHeight(rows) {
    var content = 85 + 18 + rows * (GANTT_OPTIONS.bar_height + 34);
    var avail = Math.max(360, (window.innerHeight || 800) - 300);
    return Math.min(content, avail);
  }

  var SVG_NS = 'http://www.w3.org/2000/svg';
  function drawTeamLines(meta) {
    var root = document.getElementById(GANTT_CONFIG.mountId);
    if (!root) return;
    Object.keys(meta).forEach(function (id) {
      var t = meta[id];
      var w = root.querySelector('.bar-wrapper[data-id="' + id + '"]');
      var bar = w && w.querySelector('.bar');
      if (!bar) return;
      var team = t.team || [];
      if (!team.length && !t.open_flags && !t.vault) return;
      var txt = document.createElementNS(SVG_NS, 'text');
      txt.setAttribute('class', 'gantt-team');
      txt.setAttribute('x', bar.getAttribute('x'));
      txt.setAttribute('y', (+bar.getAttribute('y')) + (+bar.getAttribute('height')) + 14);
      function span(cls, s) {
        var ts = document.createElementNS(SVG_NS, 'tspan');
        ts.setAttribute('class', cls); ts.textContent = s; txt.appendChild(ts);
      }
      team.forEach(function (m, i) {
        if (i) span('team-sep', '  ·  ');
        span('role-' + m.role, (ROLE_TAG[m.role] || m.role) + ' ' + shortName(m.name));
      });
      if (t.vault) { span('team-sep', team.length ? '  ·  ' : ''); span('team-docs', '▤ docs'); }
      if (t.open_flags) { span('team-sep', '  ·  '); span('team-flag', '⚑ ' + t.open_flags + ' lawyer flag' + (t.open_flags > 1 ? 's' : '')); }
      w.appendChild(txt);
    });
  }

  function api(method, url, body) {
    return fetch(url, {
      method: method,
      headers: { 'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json', 'X-Agent-Name': '' },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, status: r.status, data: j }; }); });
  }

  function buildPopup(ctx, meta) {
    var t = meta[String(ctx.task.id)] || {};
    ctx.set_title(esc(ctx.task.name));
    ctx.set_subtitle(esc(ctx.task.start) + ' → ' + esc(ctx.task.end) + ' · ' + esc(Math.round(ctx.task.progress || 0)) + '%');
    var rows = (t.team || []).map(function (m) {
      var contact = [m.email, m.phone].filter(Boolean).map(esc).join(' · ');
      return '<div><span class="role-' + esc(m.role) + '"><b>' + esc(m.role_label) + '</b></span> — ' + esc(m.name) +
             (contact ? ' <span class="team-sep">(' + contact + ')</span>' : '') + '</div>';
    });
    var html = rows.length ? rows.join('') : '<div class="team-sep">No team assigned</div>';
    if (t.vault) html += '<div class="team-docs">▤ Docs: ' + esc(t.vault.ref) + '</div>';
    if (t.open_flags) html += '<div class="team-flag">⚑ ' + esc(t.open_flags) + ' open lawyer flag(s)</div>';
    ctx.set_details(html);
    if (t.vault) {
      ctx.add_action('Open docs (Obsidian)', function () { window.location.href = t.vault.obsidian_url; });
      ctx.add_action('Copy agent docs URL', function () {
        var u = window.location.origin + t.vault.docs_api;
        try { navigator.clipboard.writeText(u); } catch (e) { window.prompt('Agent docs endpoint', u); }
      });
    }
    ctx.add_action('Flag lawyer', function () {
      var reason = window.prompt('Why does the lawyer need to look at this task?', '');
      if (reason === null) return;
      api('POST', '/api/gantt/tasks/' + encodeURIComponent(ctx.task.id) + '/flag-lawyer', { reason: reason })
        .then(function (res) {
          window.alert(res.ok ? 'Lawyer flagged.' : 'Could not flag: ' + ((res.data && res.data.error) || res.status));
          if (res.ok) window.LexFlowGantt.init();
        });
    });
    actionRegistry.forEach(function (a) {
      try { if (!a.when || a.when(t)) ctx.add_action(a.label, function () { a.onClick(t); }); } catch (e) { /* plug-in must not break the popup */ }
    });
  }

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
    var extras = {};
    var meta = {};
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
      // Frappe Gantt 1.2.2 calls classList.add(custom_class) — a value with a space
      // ("gantt-status-x gantt-status-overdue") throws InvalidCharacterError and kills
      // the whole chart. Pass ONE token to the library, re-apply the rest after render.
      var classes = String(t.custom_class || '').split(/\s+/).filter(Boolean);
      extras[String(t.id)] = classes.slice(1);
      meta[String(t.id)] = t;
      valid.push({
        id: String(t.id),
        name: t.name,
        start: t.start,
        end: t.end,
        progress: t.progress,
        dependencies: t.dependencies || '',
        custom_class: classes[0] || ''
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
      var opts = Object.assign({}, GANTT_OPTIONS, {
        container_height: chartHeight(valid.length),   // fixed viewport: month/week header stays glued above the bars
        padding: 34,                                    // room for the team line under each bar
        popup: function (ctx) { return buildPopup(ctx, meta); }
      });
      new Gantt('#' + GANTT_CONFIG.mountId, valid, opts);
      // Re-apply modifier classes (e.g. gantt-status-overdue) that cannot go through the library
      Object.keys(extras).forEach(function (id) {
        if (!extras[id].length) return;
        var w = document.querySelector('#' + GANTT_CONFIG.mountId + ' .bar-wrapper[data-id="' + id + '"]');
        if (w) extras[id].forEach(function (c) { w.classList.add(c); });
      });
      drawTeamLines(meta);
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
    registerAction: function (a) { if (a && a.label && typeof a.onClick === 'function') actionRegistry.push(a); },
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
