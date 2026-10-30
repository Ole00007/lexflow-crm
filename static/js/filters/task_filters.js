/* ============================================================================
 * LexFlow CRM — shared task-filter dropdown.
 * static/js/filters/task_filters.js
 *
 * One component used by the four task-tracking views (tasks, kanban, gantt,
 * graph) so there is NO copy-paste x4. It owns:
 *   - the filter STATE, persisted across the four pages under
 *     localStorage['lf_task_filter'] (so "Open only" stays on while moving
 *     tasks -> kanban -> gantt -> graph)
 *   - the compact "Filter ▾" button + dropdown panel (click-outside / Esc
 *     closes, aria-expanded, count badge, a Clear link)
 *   - the filter MATCHING logic (each view only supplies per-item features)
 *   - responsive + accessibility behaviour (390 px bottom-sheet, keyboard,
 *     dark-theme contrast via the page's own design tokens)
 *
 * Each view calls TaskFilters.create({ ... }) with:
 *   mount       Element  — toolbar/root the Filter button is appended into
 *   getItems    () -> [] — current (unfiltered) items, read at apply-time
 *   features(item, ctx)  ->  { done, blocked, priorityHigh, overdue, dueSoon,
 *                              isMine, blocksOthers }
 *     ctx = { items, myUserId, today, soon, now }  (today/soon = YYYY-MM-DD)
 *   onApply(visible, meta) — view renders/hides from the matching subset
 *     meta = { state, activeCount }
 *
 * The component itself never touches DOM specific to a view.
 * ========================================================================== */
(function () {
  'use strict';

  var KEY = 'lf_task_filter';
  var DEFAULT = { show: 'all', priority: false, due: null, assignee: 'all' };
  var FINISHED = { done: 1, closed: 1, completed: 1, archived: 1, resolved: 1 };

  function clone(o) { return { show: o.show, priority: !!o.priority, due: o.due, assignee: o.assignee }; }

  function normalize(o) {
    if (!o || typeof o !== 'object') return clone(DEFAULT);
    var s = clone(DEFAULT);
    if (o.show === 'open' || o.show === 'blocked' || o.show === 'done') s.show = o.show;
    if (o.priority) s.priority = true;
    if (o.due === 'overdue' || o.due === 'next7') s.due = o.due;
    if (o.assignee === 'mine') s.assignee = 'mine';
    return s;
  }

  function load() {
    try { return normalize(JSON.parse(localStorage.getItem(KEY))); }
    catch (e) { return clone(DEFAULT); }
  }
  function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {} }

  function activeCount(s) {
    return (s.show !== 'all' ? 1 : 0) + (s.priority ? 1 : 0) + (s.due ? 1 : 0) + (s.assignee === 'mine' ? 1 : 0);
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function dstr(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function inFinished(st) { return FINISHED[String(st || '').toLowerCase().trim()] === 1; }

  /* Central filter predicate. `f` is a view-provided feature vector. */
  function matches(s, f, today, soon) {
    if (s.show === 'open' && !!f.done) return false;
    if (s.show === 'blocked' && !f.blocked) return false;
    if (s.show === 'done' && !f.done) return false;
    /* "Most critical" = something is actually wrong or at stake: blocked, overdue, or high priority AND (blocks others OR due within 7 days).
       High priority alone is NOT enough (in real data most tasks are marked high, which would make the filter useless). */
    if (s.priority && !(f.blocked || f.overdue || (f.priorityHigh && (f.blocksOthers || f.dueSoon)))) return false;
    if (s.due === 'overdue' && !f.overdue) return false;
    if (s.due === 'next7' && !f.dueSoon) return false;
    if (s.assignee === 'mine' && !f.isMine) return false;
    return true;
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function create(options) {
    if (!options || typeof options.getItems !== 'function' ||
        typeof options.features !== 'function' || typeof options.onApply !== 'function') return null;

    var mount = options.mount || document.body;
    var state = load();
    var myUserId = null, meLoaded = false;
    var open = false;

    function token() { try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; } }

    function ensureMe(done) {
      done = done || function () {};
      if (meLoaded) { done(myUserId); return; }
      var t = token();
      if (!t) { meLoaded = true; myUserId = null; done(null); return; }
      fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + t } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          myUserId = (d && typeof d.id !== 'undefined') ? d.id : null;
          meLoaded = true;
          done(myUserId);
          if (state.assignee === 'mine') apply();   // "Mine" resolved late -> re-run
        })
        .catch(function () { meLoaded = true; myUserId = null; done(null); });
    }

    function compute() {
      var items = options.getItems() || [];
      var now = new Date();
      var today = dstr(now);
      var soon = dstr(new Date(now.getTime() + 7 * 86400000));
      var ctx = { items: items, myUserId: myUserId, today: today, soon: soon, now: now };
      return items.filter(function (it) {
        var f = options.features(it, ctx) || {};
        return matches(state, f, today, soon);
      });
    }

    function apply() {
      save(state);
      updateBadge();
      var visible = compute();
      options.onApply(visible, { state: clone(state), activeCount: activeCount(state) });
    }

    /* Re-run against the server's latest items (each view calls this after a
       data reload or re-render). */
    function refresh() { apply(); }

    function updateBadge() {
      var n = activeCount(state);
      if (n > 0) { badge.textContent = String(n); btn.setAttribute('data-active', ''); }
      else { badge.textContent = ''; btn.removeAttribute('data-active'); }
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    function sync() {
      Object.keys(showChips).forEach(function (k) { showChips[k].setAttribute('aria-pressed', state.show === k ? 'true' : 'false'); });
      priChip.setAttribute('aria-pressed', state.priority ? 'true' : 'false');
      Object.keys(dueChips).forEach(function (k) { dueChips[k].setAttribute('aria-pressed', state.due === k ? 'true' : 'false'); });
      Object.keys(asgChips).forEach(function (k) { asgChips[k].setAttribute('aria-pressed', state.assignee === k ? 'true' : 'false'); });
      apply();
    }

    /* ── Build the UI ─────────────────────────────────────────────────── */
    var root = el('div', 'lf-filter');

    var btn = el('button', 'lf-filter-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'true');
    btn.setAttribute('aria-expanded', 'false');
    btn.appendChild(el('span', 'lf-filter-label', 'Filter'));
    var caret = el('span', 'lf-filter-caret', '▾');
    caret.setAttribute('aria-hidden', 'true');
    btn.appendChild(caret);
    var badge = el('span', 'lf-filter-badge');
    badge.setAttribute('aria-hidden', 'true');
    btn.appendChild(badge);

    var panel = el('div', 'lf-filter-panel');
    panel.setAttribute('role', 'group');
    panel.setAttribute('aria-label', 'Filter tasks');

    var head = el('div', 'lf-filter-head');
    head.appendChild(el('span', null, 'Filter tasks'));
    var clearBtn = el('button', 'lf-filter-clear', 'Clear');
    clearBtn.type = 'button';
    head.appendChild(clearBtn);
    panel.appendChild(head);

    function group(labelTxt) {
      var g = el('div', 'lf-group');
      g.appendChild(el('div', 'lf-group-label', labelTxt));
      var chips = el('div', 'lf-chips');
      g.appendChild(chips);
      return { wrap: g, chips: chips };
    }

    function chip(text, isActive) {
      var c = el('button', 'lf-chip', text);
      c.type = 'button';
      c.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      return c;
    }

    var showG = group('Show');
    var showChips = {};
    ['all', 'open', 'blocked', 'done'].forEach(function (k) {
      var c = chip({ all: 'All', open: 'Open', blocked: 'Blocked', done: 'Done' }[k], state.show === k);
      c.addEventListener('click', function () { state.show = k; sync(); });
      showChips[k] = c; showG.chips.appendChild(c);
    });

    var priG = group('Priority');
    var priChip = chip('Most critical', !!state.priority);
    priChip.addEventListener('click', function () { state.priority = !state.priority; sync(); });
    priG.chips.appendChild(priChip);

    var dueG = group('Due');
    var dueChips = {};
    ['overdue', 'next7'].forEach(function (k) {
      var c = chip({ overdue: 'Overdue', next7: 'Next 7 days' }[k], state.due === k);
      c.addEventListener('click', function () { state.due = (state.due === k) ? null : k; sync(); });
      dueChips[k] = c; dueG.chips.appendChild(c);
    });

    var asgG = group('Assignee');
    var asgChips = {};
    ['all', 'mine'].forEach(function (k) {
      var c = chip({ all: 'All', mine: 'Mine' }[k], state.assignee === k);
      c.addEventListener('click', function () { state.assignee = k; sync(); });
      asgChips[k] = c; asgG.chips.appendChild(c);
    });

    [showG.wrap, priG.wrap, dueG.wrap, asgG.wrap].forEach(function (g) { panel.appendChild(g); });

    /* ── Interaction ─────────────────────────────────────────────────── */
    function toggle() { open = !open; panel.classList.toggle('open', open); updateBadge(); }
    function close() { open = false; panel.classList.remove('open'); updateBadge(); }

    btn.addEventListener('click', function (ev) { ev.stopPropagation(); toggle(); });
    clearBtn.addEventListener('click', function () { state = clone(DEFAULT); save(state); sync(); });
    document.addEventListener('click', function (e) { if (open && !root.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && open) { e.stopPropagation(); close(); btn.focus(); }
    });

    btn.setAttribute('aria-controls', panel.id);
    root.appendChild(btn);
    root.appendChild(panel);
    mount.appendChild(root);

    updateBadge();
    ensureMe();   // warm the "Mine" identity so it's ready on first use

    return {
      getState: function () { return clone(state); },
      refresh: refresh,
      apply: apply,
      close: close,
      activeCount: function () { return activeCount(state); }
    };
  }

  window.TaskFilters = {
    create: create,
    FINISHED: FINISHED,
    DEFAULT: clone(DEFAULT),
    KEY: KEY,
    inFinished: inFinished
  };
})();
