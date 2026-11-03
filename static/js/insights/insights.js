/* ============================================================================
   LexFlow CRM — Insights (WS-D) — Harvey-style usage/progress analytics.
   Pure SVG/CSS, no libraries. Fetches /api/insights/summary?range=N with the
   JWT from localStorage. All data rendered via textContent (never innerHTML
   with data). Auto-refresh every 60s, paused when the tab is hidden.
   ============================================================================ */
(function () {
  'use strict';

  var ENDPOINT = '/api/insights/summary';
  var REFRESH_MS = 60000;
  var currentRange = 30;
  var timer = null;

  // role colours (mirror crm/models/task_assignee.py TASK_ROLES + gantt.css)
  var ROLE_COLORS = {
    case_owner: '#F5B942',
    docs_supply: '#38D6D0',
    legal_assistant: '#B78CFF',
    lawyer_review: '#FF6F91'
  };
  var HEALTH_COLORS = {
    overdue: '#F59E0B',
    due_7: '#FF6F91',
    due_30: '#F5B942',
    later: '#38D6D0',
    no_date: '#7E90A9'
  };
  var HEALTH_LABELS = {
    overdue: 'Overdue',
    due_7: 'Due ≤ 7 days',
    due_30: 'Due 8–30 days',
    later: 'Due later',
    no_date: 'No date'
  };

  function $(id) { return document.getElementById(id); }
  function esc(s) { var d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }

  function getToken() {
    try { return localStorage.getItem('jwt'); } catch (e) { return null; }
  }

  function showState(id) {
    ['insights-state-loading', 'insights-state-error', 'insights-state-denied'].forEach(function (s) {
      $(s).hidden = (s !== id);
    });
    $('insights-dashboard').hidden = (id !== '');
  }

  function fetchSummary(range, cb) {
    var token = getToken();
    if (!token) { showState('insights-state-denied'); return; }
    fetch(ENDPOINT + '?range=' + encodeURIComponent(range), {
      headers: { 'Authorization': 'Bearer ' + token }
    }).then(function (r) {
      if (r.status === 401 || r.status === 422) { showState('insights-state-denied'); return null; }
      if (!r.ok) { showState('insights-state-error'); return null; }
      return r.json();
    }).then(function (data) {
      if (data) cb(data);
    }).catch(function () { showState('insights-state-error'); });
  }

  /* ── KPI cards ─────────────────────────────────────────────────────────── */
  function renderKpis(data) {
    var grid = $('kpi-grid');
    grid.textContent = '';
    var k = data.kpis || {};
    var prev = data.kpis_previous || {};
    var cards = [
      { label: 'Open matters', value: k.open_matters, prev: prev.open_matters, fmt: null },
      { label: 'Tasks done', value: k.tasks_done, prev: prev.tasks_done, fmt: null },
      { label: 'Overdue tasks', value: k.overdue_tasks, prev: prev.overdue_tasks, fmt: null },
      { label: 'Due next 7 days', value: k.due_next_7, prev: prev.due_next_7, fmt: null },
      { label: 'Avg days to first done', value: k.avg_days_open_to_first_done, prev: prev.avg_days_open_to_first_done, fmt: 'd' }
    ];
    cards.forEach(function (c) {
      var card = document.createElement('div');
      card.className = 'kpi-card';
      var lab = document.createElement('span'); lab.className = 'kpi-label'; lab.textContent = c.label;
      var val = document.createElement('span'); val.className = 'kpi-value';
      val.textContent = (c.value == null) ? '—' : (c.fmt === 'd' ? c.value + 'd' : c.value);
      card.appendChild(lab); card.appendChild(val);
      if (c.value != null && c.prev != null && c.label !== 'Avg days to first done') {
        var delta = c.value - c.prev;
        var d = document.createElement('span'); d.className = 'kpi-delta';
        if (delta > 0) { d.classList.add('up'); d.textContent = '▲ +' + delta + ' vs prev'; }
        else if (delta < 0) { d.classList.add('down'); d.textContent = '▼ ' + delta + ' vs prev'; }
        else { d.classList.add('flat'); d.textContent = '— no change'; }
        card.appendChild(d);
      }
      grid.appendChild(card);
    });
  }

  /* ── Activity area/line chart (pure SVG) ───────────────────────────────── */
  function renderActivity(data) {
    var svg = $('activity-chart');
    var empty = $('activity-empty');
    var series = data.activity || [];
    var hasData = series.some(function (w) { return w.matters_opened + w.tasks_completed + w.tasks_created > 0; });
    if (!hasData) { svg.textContent = ''; empty.hidden = false; return; }
    empty.hidden = true;

    var W = 900, H = 260, padL = 40, padR = 16, padT = 16, padB = 30;
    var iw = W - padL - padR, ih = H - padT - padB;
    var maxV = 1;
    series.forEach(function (w) {
      maxV = Math.max(maxV, w.matters_opened, w.tasks_completed, w.tasks_created);
    });
    var n = series.length;
    var x = function (i) { return padL + (n === 1 ? iw / 2 : (i / (n - 1)) * iw); };
    var y = function (v) { return padT + ih - (v / maxV) * ih; };

    var ns = 'http://www.w3.org/2000/svg';
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.textContent = '';

    // defs: gradient
    var defs = document.createElementNS(ns, 'defs');
    var grad = document.createElementNS(ns, 'linearGradient');
    grad.setAttribute('id', 'activityGrad');
    grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
    grad.setAttribute('x2', '0'); grad.setAttribute('y2', '1');
    var st1 = document.createElementNS(ns, 'stop'); st1.setAttribute('offset', '0%'); st1.setAttribute('stop-color', '#3B7DD8'); st1.setAttribute('stop-opacity', '0.35');
    var st2 = document.createElementNS(ns, 'stop'); st2.setAttribute('offset', '100%'); st2.setAttribute('stop-color', '#3B7DD8'); st2.setAttribute('stop-opacity', '0');
    grad.appendChild(st1); grad.appendChild(st2); defs.appendChild(grad);
    svg.appendChild(defs);

    // horizontal gridlines + y labels
    var ticks = 4;
    for (var t = 0; t <= ticks; t++) {
      var gy = padT + (t / ticks) * ih;
      var gl = document.createElementNS(ns, 'line');
      gl.setAttribute('class', 'grid-line');
      gl.setAttribute('x1', padL); gl.setAttribute('y1', gy);
      gl.setAttribute('x2', W - padR); gl.setAttribute('y2', gy);
      svg.appendChild(gl);
      var lab = document.createElementNS(ns, 'text');
      lab.setAttribute('class', 'axis-label');
      lab.setAttribute('x', padL - 6); lab.setAttribute('y', gy + 4);
      lab.setAttribute('text-anchor', 'end');
      lab.textContent = Math.round(maxV * (1 - t / ticks));
      svg.appendChild(lab);
    }
    // x labels (first, middle, last week)
    var xIdx = [0, Math.floor((n - 1) / 2), n - 1];
    xIdx.forEach(function (i) {
      var lab = document.createElementNS(ns, 'text');
      lab.setAttribute('class', 'axis-label');
      lab.setAttribute('x', x(i)); lab.setAttribute('y', H - 8);
      lab.setAttribute('text-anchor', 'middle');
      lab.textContent = series[i].week.slice(5);
      svg.appendChild(lab);
    });

    // series: tasks_completed (accent), matters_opened (teal), tasks_created (muted)
    var seriesDefs = [
      { key: 'tasks_completed', color: '#3B7DD8', area: true },
      { key: 'matters_opened', color: '#0F9B8E', area: false },
      { key: 'tasks_created', color: '#94A3B8', area: false }
    ];
    seriesDefs.forEach(function (sd) {
      var pts = series.map(function (w, i) { return [x(i), y(w[sd.key])]; });
      if (sd.area) {
        var area = document.createElementNS(ns, 'path');
        var d = 'M ' + pts[0][0] + ' ' + (padT + ih);
        pts.forEach(function (p) { d += ' L ' + p[0] + ' ' + p[1]; });
        d += ' L ' + pts[pts.length - 1][0] + ' ' + (padT + ih) + ' Z';
        area.setAttribute('class', 'area-fill');
        area.setAttribute('d', d);
        svg.appendChild(area);
      }
      var line = document.createElementNS(ns, 'path');
      var ld = 'M ' + pts[0][0] + ' ' + pts[0][1];
      for (var i = 1; i < pts.length; i++) { ld += ' L ' + pts[i][0] + ' ' + pts[i][1]; }
      line.setAttribute('class', 'line');
      line.setAttribute('stroke', sd.color);
      line.setAttribute('d', ld);
      svg.appendChild(line);
      // dots + tooltip
      pts.forEach(function (p, i) {
        var dot = document.createElementNS(ns, 'circle');
        dot.setAttribute('class', 'dot');
        dot.setAttribute('cx', p[0]); dot.setAttribute('cy', p[1]);
        dot.setAttribute('r', 3); dot.setAttribute('fill', sd.color);
        dot.setAttribute('data-key', sd.key);
        dot.setAttribute('data-week', series[i].week);
        dot.setAttribute('data-val', series[i][sd.key]);
        svg.appendChild(dot);
      });
    });

    // legend
    var lx = padL;
    seriesDefs.forEach(function (sd) {
      var sw = document.createElementNS(ns, 'rect');
      sw.setAttribute('x', lx); sw.setAttribute('y', padT - 10); sw.setAttribute('width', 10); sw.setAttribute('height', 3);
      sw.setAttribute('fill', sd.color);
      svg.appendChild(sw);
      var lab = document.createElementNS(ns, 'text');
      lab.setAttribute('class', 'legend-text');
      lab.setAttribute('x', lx + 14); lab.setAttribute('y', padT - 6);
      lab.textContent = sd.key.replace(/_/g, ' ');
      svg.appendChild(lab);
      lx += 14 + sd.key.replace(/_/g, ' ').length * 6.5 + 16;
    });

    // tooltip on hover over dots
    var tip = $('insights-tip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'insights-tip'; tip.className = 'tip'; tip.hidden = true;
      document.body.appendChild(tip);
    }
    svg.addEventListener('mousemove', function (e) {
      var t = e.target;
      if (t && t.getAttribute && t.getAttribute('data-key')) {
        tip.textContent = t.getAttribute('data-week') + ' · ' +
          t.getAttribute('data-key').replace(/_/g, ' ') + ': ' + t.getAttribute('data-val');
        tip.hidden = false;
        var rect = svg.getBoundingClientRect();
        tip.style.left = (e.clientX - rect.left + 12) + 'px';
        tip.style.top = (e.clientY - rect.top - 10) + 'px';
      } else {
        tip.hidden = true;
      }
    });
    svg.addEventListener('mouseleave', function () { tip.hidden = true; });
  }

  /* ── Horizontal bars (status / workload) ───────────────────────────────── */
  function renderHBars(containerId, emptyId, rows, colorFn, labelKey) {
    var box = $(containerId);
    var empty = $(emptyId);
    box.textContent = '';
    var has = rows.some(function (r) { return r.count > 0; });
    if (!has) { empty.hidden = false; return; }
    empty.hidden = true;
    var max = 1;
    rows.forEach(function (r) { max = Math.max(max, r.count); });
    rows.forEach(function (r) {
      var row = document.createElement('div'); row.className = 'hbar-row';
      var lab = document.createElement('span'); lab.className = 'hbar-label'; lab.textContent = r[labelKey];
      var track = document.createElement('div'); track.className = 'hbar-track';
      var fill = document.createElement('div'); fill.className = 'hbar-fill';
      fill.style.width = (r.count / max * 100) + '%';
      fill.style.background = colorFn(r);
      track.appendChild(fill);
      var cnt = document.createElement('span'); cnt.className = 'hbar-count'; cnt.textContent = r.count;
      row.appendChild(lab); row.appendChild(track); row.appendChild(cnt);
      box.appendChild(row);
    });
  }

  /* ── Deadline health ring (segmented) ─────────────────────────────────── */
  function renderHealth(data) {
    var wrap = $('health-ring');
    var legend = $('health-legend');
    var empty = $('health-empty');
    var h = data.deadline_health || {};
    var order = ['overdue', 'due_7', 'due_30', 'later', 'no_date'];
    var total = order.reduce(function (s, k) { return s + (h[k] || 0); }, 0);
    if (total === 0) { wrap.textContent = ''; legend.textContent = ''; empty.hidden = false; return; }
    empty.hidden = true;

    var ns = 'http://www.w3.org/2000/svg';
    var size = 180, cx = size / 2, cy = size / 2, r = 70, sw = 18;
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'ring-svg');
    svg.setAttribute('viewBox', '0 0 ' + size + ' ' + size);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Deadline health: ' + total + ' open tasks');
    var track = document.createElementNS(ns, 'circle');
    track.setAttribute('class', 'ring-track');
    track.setAttribute('cx', cx); track.setAttribute('cy', cy); track.setAttribute('r', r);
    svg.appendChild(track);

    var start = -Math.PI / 2;
    order.forEach(function (k) {
      var n = h[k] || 0;
      if (n === 0) return;
      var frac = n / total;
      var end = start + frac * 2 * Math.PI;
      var x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start);
      var x2 = cx + r * Math.cos(end), y2 = cy + r * Math.sin(end);
      var large = (end - start) > Math.PI ? 1 : 0;
      var seg = document.createElementNS(ns, 'path');
      seg.setAttribute('class', 'ring-seg');
      seg.setAttribute('stroke', HEALTH_COLORS[k]);
      seg.setAttribute('d', 'M ' + x1 + ' ' + y1 + ' A ' + r + ' ' + r + ' 0 ' + large + ' 1 ' + x2 + ' ' + y2);
      svg.appendChild(seg);
      start = end;
    });
    var cval = document.createElementNS(ns, 'text');
    cval.setAttribute('class', 'ring-center'); cval.setAttribute('x', cx); cval.setAttribute('y', cy - 2); cval.setAttribute('text-anchor', 'middle');
    cval.textContent = total;
    var csub = document.createElementNS(ns, 'text');
    csub.setAttribute('class', 'ring-center-sub'); csub.setAttribute('x', cx); csub.setAttribute('y', cy + 18); csub.setAttribute('text-anchor', 'middle');
    csub.textContent = 'open tasks';
    svg.appendChild(cval); svg.appendChild(csub);
    wrap.textContent = ''; wrap.appendChild(svg);

    legend.textContent = '';
    order.forEach(function (k) {
      var li = document.createElement('li');
      var sw = document.createElement('span'); sw.className = 'swatch'; sw.style.background = HEALTH_COLORS[k];
      var lab = document.createElement('span'); lab.textContent = HEALTH_LABELS[k];
      var cnt = document.createElement('span'); cnt.className = 'hcount'; cnt.textContent = h[k] || 0;
      li.appendChild(sw); li.appendChild(lab); li.appendChild(cnt);
      legend.appendChild(li);
    });
  }

  /* ── Workload: role bars + member chips ────────────────────────────────── */
  function renderWorkload(data) {
    var wl = data.workload_by_role || {};
    var rows = (wl.by_role || []).map(function (r) {
      return { label: r.label, count: r.count, color: ROLE_COLORS[r.role] || r.color };
    });
    renderHBars('workload-bars', 'workload-empty', rows, function (r) { return r.color; }, 'label');

    var list = $('member-list');
    list.textContent = '';
    (wl.by_member || []).forEach(function (m) {
      var chip = document.createElement('span'); chip.className = 'member-chip';
      var ini = document.createElement('span'); ini.textContent = m.initials;
      var cnt = document.createElement('span'); cnt.className = 'mcount'; cnt.textContent = m.count;
      chip.appendChild(ini); chip.appendChild(cnt);
      list.appendChild(chip);
    });
  }

  /* ── Flag stats ────────────────────────────────────────────────────────── */
  function renderFlags(data) {
    var box = $('flag-stats');
    var empty = $('flags-empty');
    var f = data.flags || {};
    box.textContent = '';
    if (!f.open && !f.resolved_in_range) { empty.hidden = false; return; }
    empty.hidden = true;
    var stats = [
      { label: 'Open flags', value: f.open },
      { label: 'Resolved in range', value: f.resolved_in_range },
      { label: 'Median hours to resolve', value: (f.median_hours_to_resolve == null ? '—' : f.median_hours_to_resolve) }
    ];
    stats.forEach(function (s) {
      var el = document.createElement('div'); el.className = 'flag-stat';
      var lab = document.createElement('div'); lab.className = 'fs-label'; lab.textContent = s.label;
      var val = document.createElement('div'); val.className = 'fs-value'; val.textContent = s.value;
      el.appendChild(lab); el.appendChild(val);
      box.appendChild(el);
    });
  }

  /* ── Table toggle ─────────────────────────────────────────────────────── */
  function renderTable(data) {
    var box = $('insights-table');
    box.textContent = '';
    var table = document.createElement('table');
    var thead = document.createElement('thead');
    var hrow = document.createElement('tr');
    ['Metric', 'Value'].forEach(function (h) {
      var th = document.createElement('th'); th.textContent = h; hrow.appendChild(th);
    });
    thead.appendChild(hrow); table.appendChild(thead);
    var tbody = document.createElement('tbody');
    var k = data.kpis || {};
    var rows = [
      ['Open matters', k.open_matters],
      ['Tasks done in range', k.tasks_done],
      ['Overdue tasks', k.overdue_tasks],
      ['Due next 7 days', k.due_next_7],
      ['Avg days to first done', k.avg_days_open_to_first_done == null ? '—' : k.avg_days_open_to_first_done]
    ];
    (data.matters_by_status || []).forEach(function (m) { rows.push(['Matters · ' + m.status, m.count]); });
    var h = data.deadline_health || {};
    Object.keys(HEALTH_LABELS).forEach(function (key) { rows.push(['Deadline · ' + HEALTH_LABELS[key], h[key] || 0]); });
    (data.workload_by_role.by_role || []).forEach(function (r) { rows.push(['Workload · ' + r.label, r.count]); });
    (data.workload_by_role.by_member || []).forEach(function (m) { rows.push(['Workload · ' + m.initials, m.count]); });
    var f = data.flags || {};
    rows.push(['Open flags', f.open], ['Resolved in range', f.resolved_in_range],
      ['Median hours to resolve', f.median_hours_to_resolve == null ? '—' : f.median_hours_to_resolve]);
    rows.forEach(function (r) {
      var tr = document.createElement('tr');
      var td1 = document.createElement('td'); td1.textContent = r[0];
      var td2 = document.createElement('td'); td2.textContent = r[1];
      tr.appendChild(td1); tr.appendChild(td2); tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    box.appendChild(table);
  }

  /* ── Main render ───────────────────────────────────────────────────────── */
  function render(data) {
    renderKpis(data);
    renderActivity(data);
    renderHBars('status-bars', 'status-empty', data.matters_by_status || [], function () { return '#3B7DD8'; }, 'status');
    renderHealth(data);
    renderWorkload(data);
    renderFlags(data);
    renderTable(data);
    showState('');
  }

  function load() {
    showState('insights-state-loading');
    fetchSummary(currentRange, render);
  }

  /* ── Range switcher ────────────────────────────────────────────────────── */
  function bindRange() {
    var btns = document.querySelectorAll('.range-btn');
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        btns.forEach(function (x) { x.classList.remove('is-active'); });
        b.classList.add('is-active');
        currentRange = parseInt(b.getAttribute('data-range'), 10);
        load();
      });
    });
  }

  /* ── Table toggle ──────────────────────────────────────────────────────── */
  function bindTable() {
    var btn = $('table-toggle');
    btn.addEventListener('click', function () {
      var box = $('insights-table');
      var open = box.hidden;
      box.hidden = !open;
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.textContent = open ? 'Hide table' : 'View as table';
    });
  }

  /* ── Auto-refresh (pause when tab hidden) ──────────────────────────────── */
  function startRefresh() {
    if (timer) clearInterval(timer);
    timer = setInterval(function () {
      if (!document.hidden) load();
    }, REFRESH_MS);
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindRange();
    bindTable();
    load();
    startRefresh();
  });
})();
