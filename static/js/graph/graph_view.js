/* LexFlow — live context graph (Obsidian-style).
 *
 * Read-only. Data: GET /api/roadmap/graph  ({nodes:[{id,type,label,data}], edges:[{source,target,type,label}]})
 * Auth: JWT in localStorage['jwt'] sent as Bearer (same contract as gantt_view.js);
 *       all authorization / workspace isolation lives on the endpoint.
 * No dependencies, no inline JS (production CSP is script-src 'self').
 */
(function () {
  'use strict';

  var ENDPOINT = '/api/roadmap/graph';
  var POLL_MS = 30000;
  var FINISHED = { done: 1, closed: 1, completed: 1, archived: 1, resolved: 1, won: 1, lost: 1 };

  var TYPE = {
    case:    { color: '#3B7DD8', label: 'Cases',    href: '/kanban' },
    task:    { color: '#10B981', label: 'Tasks',    href: '/tasks' },
    contact: { color: '#F59E0B', label: 'Contacts', href: '/contacts' },
    staff:   { color: '#A78BFA', label: 'Staff',    href: '/workspace' },
    event:   { color: '#0F9B8E', label: 'Events',   href: '/calendar' },
    status:  { color: '#7E90A9', label: 'Statuses', href: null }
  };
  var TODAY_COLOR = { overdue: '#EF4444', today: '#F59E0B', active: '#3B7DD8', soon: '#7E90A9' };

  var $ = function (id) { return document.getElementById(id); };
  var canvas = $('gp-canvas');
  if (!canvas) { return; }
  var ctx = canvas.getContext('2d');

  var state = {
    nodes: [], edges: [], byId: {}, adj: {},
    hidden: {},            // type -> true
    todayMode: false, localMode: false,
    selected: null, hover: null, query: '',
    view: { x: 0, y: 0, k: 1 },
    alpha: 1, w: 0, h: 0, dpr: window.devicePixelRatio || 1,
    drag: null, pan: null, lastUpdate: null, didFit: false
  };

  /* ── helpers ───────────────────────────────────────────────────────── */
  function token() { try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; } }
  function startOfDay(d) { var x = new Date(d); x.setHours(0, 0, 0, 0); return x; }
  function parseDate(s) { if (!s) { return null; } var d = new Date(s); return isNaN(d) ? null : d; }
  function fmtDate(s) { var d = parseDate(s); return d ? d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '—'; }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) { e.className = cls; } if (text != null) { e.textContent = text; } return e; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function shortLabel(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

  /* ── data ──────────────────────────────────────────────────────────── */
  function classify(n) {
    // today-ness for case/task nodes: overdue | today | active | soon | null
    if (n.type !== 'task' && n.type !== 'case') { return null; }
    var d = n.data || {};
    var status = String(d.status || '').toLowerCase();
    if (FINISHED[status]) { return null; }
    var due = parseDate(d.duedate);
    var t0 = startOfDay(new Date()).getTime();
    if (due) {
      var dd = startOfDay(due).getTime();
      if (dd < t0) { return 'overdue'; }
      if (dd === t0) { return 'today'; }
    }
    if (status === 'in_progress' || status === 'active' || status === 'open' || status === 'in progress') { return 'active'; }
    if (due) {
      var diff = (startOfDay(due).getTime() - t0) / 86400000;
      if (diff <= 7) { return 'soon'; }
    }
    return null;
  }

  function ingest(payload) {
    var old = state.byId, nodes = [], byId = {}, adj = {}, i;
    var incoming = payload.nodes || [];
    var cx = state.w / 2, cy = state.h / 2;
    for (i = 0; i < incoming.length; i++) {
      var raw = incoming[i], prev = old[raw.id];
      var n = prev || { id: raw.id, x: 0, y: 0, vx: 0, vy: 0, fixed: false, isNew: true };
      if (!prev) {
        var ang = Math.random() * Math.PI * 2, r = 60 + Math.random() * 220;
        n.x = cx + Math.cos(ang) * r; n.y = cy + Math.sin(ang) * r;
      }
      n.type = raw.type; n.label = raw.label || raw.id; n.data = raw.data || {};
      n.today = classify(n); n.deg = 0;
      nodes.push(n); byId[n.id] = n; adj[n.id] = {};
    }
    var edges = [];
    (payload.edges || []).forEach(function (e) {
      var a = byId[e.source], b = byId[e.target];
      if (!a || !b) { return; }
      edges.push({ a: a, b: b, type: e.type, label: e.label });
      a.deg++; b.deg++; adj[a.id][b.id] = 1; adj[b.id][a.id] = 1;
    });
    var added = nodes.filter(function (n) { return n.isNew; }).length;
    nodes.forEach(function (n) { n.isNew = false; n.r = clamp(5 + Math.sqrt(n.deg) * 2.2, 5, 14); });
    state.nodes = nodes; state.edges = edges; state.byId = byId; state.adj = adj;
    if (state.selected && !byId[state.selected]) { state.selected = null; }
    if (added || !state.didFit) { state.alpha = Math.max(state.alpha, added ? 0.6 : 1); }
    buildTypeChips(); renderToday(); renderDetail();
  }

  function load(manual) {
    var t = token();
    if (!t) { showState('Sign in to see your context graph.'); setLive('signed out', true); return Promise.resolve(); }
    return fetch(ENDPOINT, { headers: { 'Authorization': 'Bearer ' + t, 'Accept': 'application/json' }, credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { throw new Error('denied'); }
        if (!r.ok) { throw new Error('http ' + r.status); }
        return r.json();
      })
      .then(function (j) {
        ingest(j);
        state.lastUpdate = new Date();
        if (!state.nodes.length) { showState('Nothing to show yet — create a case or task and it appears here.'); }
        else { showState(null); if (!state.didFit) { fitView(); state.didFit = true; } }
        setLive('live · ' + state.nodes.length + ' nodes · ' + state.edges.length + ' links · ' + state.lastUpdate.toLocaleTimeString(), false);
      })
      .catch(function (e) {
        if (e.message === 'denied') { showState('Your session has expired — sign in again.'); setLive('session expired', true); }
        else if (!state.nodes.length) { showState('Could not load the graph (' + e.message + ').'); setLive('error', true); }
        else { setLive('offline — showing last data', true); }
      });
  }

  function showState(msg) { var s = $('gp-state'); if (msg) { s.textContent = msg; s.style.display = 'flex'; } else { s.style.display = 'none'; } }
  function setLive(text, err) { $('gp-live-text').textContent = text; $('gp-live').className = 'gp-live' + (err ? ' err' : ''); }

  /* ── visibility rules ──────────────────────────────────────────────── */
  function neighborsOf(id, depth) {
    var seen = {}; seen[id] = 1; var frontier = [id];
    for (var d = 0; d < depth; d++) {
      var next = [];
      frontier.forEach(function (f) { Object.keys(state.adj[f] || {}).forEach(function (k) { if (!seen[k]) { seen[k] = 1; next.push(k); } }); });
      frontier = next;
    }
    return seen;
  }
  var focusSet = null;
  function recomputeFocus() {
    focusSet = null;
    if (state.localMode && state.selected) { focusSet = neighborsOf(state.selected, 2); }
  }
  function isVisible(n) {
    if (state.hidden[n.type]) { return false; }
    if (focusSet && !focusSet[n.id]) { return false; }
    return true;
  }
  function emphasis(n) {
    // 1 = full, 0.18 = dimmed
    var q = state.query;
    if (q && String(n.label).toLowerCase().indexOf(q) === -1) { return 0.14; }
    if (state.todayMode) {
      if (n.today) { return 1; }
      var nb = state.adj[n.id] || {};
      for (var k in nb) { if (state.byId[k] && state.byId[k].today) { return 0.45; } }
      return 0.12;
    }
    if (state.hover || state.selected) {
      var f = state.hover || state.selected;
      if (n.id === f || (state.adj[f] && state.adj[f][n.id])) { return 1; }
      return 0.22;
    }
    return 1;
  }

  /* ── physics ───────────────────────────────────────────────────────── */
  function tick() {
    var nodes = state.nodes, i, j, n, m, dx, dy, d2, d, f;
    if (state.alpha < 0.005) { return; }
    var a = state.alpha, cx = state.w / 2 / state.view.k - state.view.x / state.view.k, cy = state.h / 2 / state.view.k - state.view.y / state.view.k;
    cx = (state.w / 2 - state.view.x) / state.view.k; cy = (state.h / 2 - state.view.y) / state.view.k;
    var vis = nodes.filter(isVisible);
    for (i = 0; i < vis.length; i++) {
      n = vis[i];
      for (j = i + 1; j < vis.length; j++) {
        m = vis[j]; dx = n.x - m.x; dy = n.y - m.y; d2 = dx * dx + dy * dy;
        if (d2 > 90000) { continue; }
        if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        d = Math.sqrt(d2); f = (4200 * a) / d2;
        n.vx += dx / d * f; n.vy += dy / d * f; m.vx -= dx / d * f; m.vy -= dy / d * f;
      }
    }
    state.edges.forEach(function (e) {
      if (!isVisible(e.a) || !isVisible(e.b)) { return; }
      var weak = e.type === 'status' || e.type === 'assigned_to';   // hubs (status / the one owner) must not collapse the graph
      dx = e.b.x - e.a.x; dy = e.b.y - e.a.y; d = Math.sqrt(dx * dx + dy * dy) || 1;
      f = (d - (weak ? 220 : 70)) * (weak ? 0.004 : 0.045) * a; var fx = dx / d * f, fy = dy / d * f;
      e.a.vx += fx; e.a.vy += fy; e.b.vx -= fx; e.b.vy -= fy;
    });
    vis.forEach(function (n) {
      n.vx += (cx - n.x) * 0.012 * a; n.vy += (cy - n.y) * 0.012 * a;
      if (n.fixed) { n.vx = 0; n.vy = 0; return; }
      n.vx *= 0.82; n.vy *= 0.82; n.x += n.vx; n.y += n.vy;
    });
    state.alpha *= 0.985;
  }

  /* ── drawing ───────────────────────────────────────────────────────── */
  function css(name, fb) { var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim(); return v || fb; }
  function draw() {
    var v = state.view, W = state.w, H = state.h;
    ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.save(); ctx.translate(v.x, v.y); ctx.scale(v.k, v.k);
    var textCol = css('--text', '#E2E8F0'), faint = css('--text-faint', '#7E90A9');
    var focus = state.hover || state.selected;

    state.edges.forEach(function (e) {
      if (!isVisible(e.a) || !isVisible(e.b)) { return; }
      var em = Math.min(emphasis(e.a), emphasis(e.b));
      var on = focus && (e.a.id === focus || e.b.id === focus);
      ctx.globalAlpha = on ? 0.95 : ((e.type === 'status' || e.type === 'assigned_to') ? 0.14 : 0.55) * em;
      ctx.strokeStyle = on ? css('--accent-h', '#5A96F0') : faint;
      ctx.lineWidth = (on ? 1.8 : 1) / v.k;
      ctx.beginPath(); ctx.moveTo(e.a.x, e.a.y); ctx.lineTo(e.b.x, e.b.y); ctx.stroke();
    });

    var drawLabels = [];
    state.nodes.forEach(function (n) {
      if (!isVisible(n)) { return; }
      var em = emphasis(n), col = (TYPE[n.type] || TYPE.status).color;
      ctx.globalAlpha = em;
      if (n.today && (state.todayMode || em === 1)) {      // halo for things that need attention today
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 5, 0, 6.2832);
        ctx.strokeStyle = TODAY_COLOR[n.today]; ctx.lineWidth = 2 / v.k; ctx.globalAlpha = em * 0.9; ctx.stroke(); ctx.globalAlpha = em;
      }
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.2832);
      ctx.fillStyle = col; ctx.fill();
      if (n.id === state.selected) { ctx.lineWidth = 2.5 / v.k; ctx.strokeStyle = '#fff'; ctx.stroke(); }
      var show = n.id === state.selected || n.id === state.hover || (!state.todayMode && n.deg >= 4 && v.k > 0.7) || (!state.todayMode && v.k > 1.35) || (state.todayMode && n.today && v.k > 0.55) || (state.query && em === 1);
      if (show && em > 0.3) { drawLabels.push(n); }
    });
    ctx.globalAlpha = 1;
    ctx.font = (12 / Math.max(v.k, 0.8)) + 'px -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    var placed = [];
    drawLabels.sort(function (a, b) {
      var pa = (a.id === state.selected || a.id === state.hover ? 1000 : 0) + (a.today ? 50 : 0) + a.deg;
      var pb = (b.id === state.selected || b.id === state.hover ? 1000 : 0) + (b.today ? 50 : 0) + b.deg;
      return pb - pa;
    });
    drawLabels.forEach(function (n) {
      var t = shortLabel(n.label, 34), y = n.y + n.r + 3, w = ctx.measureText(t).width, hgt = 15 / Math.max(v.k, 0.8);
      var box = { x0: n.x - w / 2 - 2, x1: n.x + w / 2 + 2, y0: y - 1, y1: y + hgt };
      var must = n.id === state.selected || n.id === state.hover;
      if (!must) {
        for (var q = 0; q < placed.length; q++) {
          var p = placed[q];
          if (box.x0 < p.x1 && box.x1 > p.x0 && box.y0 < p.y1 && box.y1 > p.y0) { return; }
        }
      }
      placed.push(box);
      ctx.lineWidth = 3 / v.k; ctx.strokeStyle = css('--bg', '#0E1117'); ctx.strokeText(t, n.x, y);
      ctx.fillStyle = textCol; ctx.fillText(t, n.x, y);
    });
    ctx.restore();
  }

  function frame() { tick(); draw(); requestAnimationFrame(frame); }

  /* ── view / interaction ────────────────────────────────────────────── */
  function toWorld(px, py) { return { x: (px - state.view.x) / state.view.k, y: (py - state.view.y) / state.view.k }; }
  function pick(px, py) {
    var w = toWorld(px, py), best = null, bd = 1e9;
    state.nodes.forEach(function (n) {
      if (!isVisible(n)) { return; }
      var dx = n.x - w.x, dy = n.y - w.y, d = Math.sqrt(dx * dx + dy * dy), hit = n.r + 4 / state.view.k;
      if (d < hit && d < bd) { best = n; bd = d; }
    });
    return best;
  }
  function fitView() {
    var vis = state.nodes.filter(isVisible);
    if (!vis.length || !state.w) { return; }
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    vis.forEach(function (n) { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y); x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y); });
    var pad = 60, k = clamp(Math.min((state.w - pad * 2) / Math.max(x1 - x0, 80), (state.h - pad * 2) / Math.max(y1 - y0, 80)), 0.2, 1.6);
    state.view.k = k; state.view.x = state.w / 2 - ((x0 + x1) / 2) * k; state.view.y = state.h / 2 - ((y0 + y1) / 2) * k;
  }
  function centerOn(n) { state.view.x = state.w / 2 - n.x * state.view.k; state.view.y = state.h / 2 - n.y * state.view.k; }
  function zoomAt(px, py, factor) {
    var v = state.view, nk = clamp(v.k * factor, 0.15, 4), w = toWorld(px, py);
    v.k = nk; v.x = px - w.x * nk; v.y = py - w.y * nk;
  }
  function select(id, center) {
    state.selected = id; recomputeFocus(); renderDetail(); renderToday();
    if (id && center && state.byId[id]) { centerOn(state.byId[id]); }
    state.alpha = Math.max(state.alpha, 0.3);
  }

  function rectPos(ev) { var r = canvas.getBoundingClientRect(); return { x: ev.clientX - r.left, y: ev.clientY - r.top }; }
  canvas.addEventListener('pointerdown', function (ev) {
    var p = rectPos(ev), n = pick(p.x, p.y);
    canvas.setPointerCapture(ev.pointerId);
    if (n) { state.drag = { n: n, moved: false }; n.fixed = true; }
    else { state.pan = { sx: p.x, sy: p.y, vx: state.view.x, vy: state.view.y, moved: false }; }
    canvas.classList.add('dragging');
  });
  canvas.addEventListener('pointermove', function (ev) {
    var p = rectPos(ev);
    if (state.drag) {
      var w = toWorld(p.x, p.y); state.drag.n.x = w.x; state.drag.n.y = w.y; state.drag.moved = true; state.alpha = Math.max(state.alpha, 0.25);
    } else if (state.pan) {
      state.pan.moved = true; state.view.x = state.pan.vx + (p.x - state.pan.sx); state.view.y = state.pan.vy + (p.y - state.pan.sy);
    } else {
      var h = pick(p.x, p.y); state.hover = h ? h.id : null; canvas.style.cursor = h ? 'pointer' : 'grab';
    }
  });
  function endPointer(ev) {
    var p = rectPos(ev);
    if (state.drag) {
      var d = state.drag; d.n.fixed = false;
      if (!d.moved) { select(d.n.id, false); }
    } else if (state.pan && !state.pan.moved) { select(null, false); }
    state.drag = null; state.pan = null; canvas.classList.remove('dragging');
  }
  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('pointerleave', function () { if (!state.drag && !state.pan) { state.hover = null; } });
  canvas.addEventListener('dblclick', function (ev) {
    var p = rectPos(ev), n = pick(p.x, p.y);
    if (n) { select(n.id, true); setMode('local', true); }
  });
  canvas.addEventListener('wheel', function (ev) {
    ev.preventDefault(); var p = rectPos(ev); zoomAt(p.x, p.y, ev.deltaY < 0 ? 1.12 : 1 / 1.12);
  }, { passive: false });
  $('gp-zin').addEventListener('click', function () { zoomAt(state.w / 2, state.h / 2, 1.25); });
  $('gp-zout').addEventListener('click', function () { zoomAt(state.w / 2, state.h / 2, 0.8); });
  $('gp-fit').addEventListener('click', fitView);

  function resize() {
    var r = canvas.parentNode.getBoundingClientRect();
    state.w = r.width; state.h = r.height; state.dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(r.width * state.dpr); canvas.height = Math.round(r.height * state.dpr);
  }
  if (window.ResizeObserver) { new ResizeObserver(resize).observe(canvas.parentNode); } else { window.addEventListener('resize', resize); }

  /* ── controls ──────────────────────────────────────────────────────── */
  function setMode(which, on) {
    if (which === 'today') { state.todayMode = on; $('gp-mode-today').classList.toggle('on', on); $('gp-mode-today').setAttribute('aria-pressed', on); }
    if (which === 'local') {
      state.localMode = on && !!state.selected; $('gp-mode-local').classList.toggle('on', state.localMode); $('gp-mode-local').setAttribute('aria-pressed', state.localMode);
      recomputeFocus(); state.alpha = Math.max(state.alpha, 0.5);
      if (!on || !state.selected) { setTimeout(fitView, 30); } else { setTimeout(fitView, 400); }
    }
  }
  function bindChip(id, which) {
    var c = $(id);
    function toggle() { setMode(which, !(which === 'today' ? state.todayMode : state.localMode)); }
    c.addEventListener('click', toggle);
    c.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
  }
  bindChip('gp-mode-today', 'today'); bindChip('gp-mode-local', 'local');
  $('gp-search').addEventListener('input', function (e) { state.query = e.target.value.trim().toLowerCase(); });

  function buildTypeChips() {
    var host = $('gp-type-chips'), counts = {};
    state.nodes.forEach(function (n) { counts[n.type] = (counts[n.type] || 0) + 1; });
    host.textContent = '';
    Object.keys(TYPE).forEach(function (t) {
      if (!counts[t]) { return; }
      var c = el('span', 'chip' + (state.hidden[t] ? ' off' : '')); c.setAttribute('role', 'button'); c.tabIndex = 0;
      var dot = el('i'); dot.style.background = TYPE[t].color; c.appendChild(dot);
      c.appendChild(document.createTextNode(TYPE[t].label + ' ' + counts[t]));
      function toggle() { state.hidden[t] = !state.hidden[t]; recomputeFocus(); state.alpha = Math.max(state.alpha, 0.4); buildTypeChips(); }
      c.addEventListener('click', toggle);
      c.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
      host.appendChild(c); host.appendChild(document.createTextNode(' '));
    });
  }

  /* ── side panels ───────────────────────────────────────────────────── */
  function renderToday() {
    var host = $('gp-today'); host.textContent = '';
    var groups = [['overdue', 'Overdue'], ['today', 'Due today'], ['active', 'In progress'], ['soon', 'Next 7 days']];
    var any = false;
    groups.forEach(function (g) {
      var items = state.nodes.filter(function (n) { return n.today === g[0]; });
      if (!items.length) { return; }
      any = true;
      items.sort(function (a, b) { return String(a.data.duedate || '9').localeCompare(String(b.data.duedate || '9')); });
      var box = el('div', 'gp-today-group'), h = el('h3'); h.appendChild(el('b', null, g[1])); h.appendChild(el('span', null, String(items.length)));
      h.firstChild.style.color = TODAY_COLOR[g[0]]; box.appendChild(h);
      items.slice(0, 8).forEach(function (n) {
        var row = el('div', 'gp-row' + (n.id === state.selected ? ' sel' : '')); row.tabIndex = 0;
        var dot = el('i'); dot.style.background = (TYPE[n.type] || TYPE.status).color; row.appendChild(dot);
        row.appendChild(el('span', 't', n.label)); row.appendChild(el('em', null, n.data.duedate ? fmtDate(n.data.duedate) : ''));
        function go() { select(n.id, true); }
        row.addEventListener('click', go); row.addEventListener('keydown', function (e) { if (e.key === 'Enter') { go(); } });
        box.appendChild(row);
      });
      if (items.length > 8) { box.appendChild(el('div', 'gp-empty', '+' + (items.length - 8) + ' more')); }
      host.appendChild(box);
    });
    if (!any) { host.appendChild(el('p', 'gp-empty', 'Nothing overdue, due today or in progress. Quiet day.')); }
  }

  function renderDetail() {
    var host = $('gp-detail'); host.textContent = '';
    var n = state.selected && state.byId[state.selected];
    if (!n) { host.appendChild(el('p', 'gp-empty', 'Click a node to see its context.')); return; }
    host.appendChild(el('p', 'gp-detail-title', n.label));
    var dl = el('dl', 'gp-detail');
    function row(k, v) { if (v == null || v === '') { return; } dl.appendChild(el('dt', null, k)); dl.appendChild(el('dd', null, String(v))); }
    var d = n.data;
    row('Type', n.type); row('Status', d.status); row('Priority', d.priority);
    if (d.duedate) { row('Due', fmtDate(d.duedate)); }
    if (n.today) { row('Today', { overdue: 'Overdue', today: 'Due today', active: 'In progress', soon: 'Due within 7 days' }[n.today]); }
    row('Email', d.email); row('Phone', d.phone); row('Company', d.company); row('Role', d.role);
    if (d.start_datetime) { row('Starts', fmtDate(d.start_datetime)); }
    row('Links', Object.keys(state.adj[n.id] || {}).length);
    host.appendChild(dl);
    var rel = Object.keys(state.adj[n.id] || {}).map(function (k) { return state.byId[k]; }).filter(Boolean);
    if (rel.length) {
      var h = el('h2', null, 'Connected'); h.style.marginTop = '12px'; host.appendChild(h);
      rel.slice(0, 12).forEach(function (m) {
        var r = el('div', 'gp-row'); r.tabIndex = 0;
        var dot = el('i'); dot.style.background = (TYPE[m.type] || TYPE.status).color; r.appendChild(dot);
        r.appendChild(el('span', 't', m.label)); r.appendChild(el('em', null, m.type));
        r.addEventListener('click', function () { select(m.id, true); });
        r.addEventListener('keydown', function (e) { if (e.key === 'Enter') { select(m.id, true); } });
        host.appendChild(r);
      });
    }
    var act = el('div', 'gp-actions');
    var tinfo = TYPE[n.type];
    if (tinfo && tinfo.href) { var a = el('a', 'gp-btn', 'Open in ' + tinfo.label.toLowerCase()); a.href = tinfo.href; act.appendChild(a); }
    var f = el('button', 'gp-btn', 'Focus neighbourhood'); f.type = 'button'; f.addEventListener('click', function () { setMode('local', true); }); act.appendChild(f);
    host.appendChild(act);
  }

  /* ── boot ──────────────────────────────────────────────────────────── */
  resize();
  requestAnimationFrame(frame);
  load();
  setInterval(function () { if (!document.hidden) { load(); } }, POLL_MS);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) { load(); } });
  window.__lexGraph = { state: state, reload: load };   // handy for debugging in devtools
})();
