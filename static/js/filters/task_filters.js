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
 *   - an always-visible "Filters on — N — Showing X of Y — Clear" banner that
 *     appears next to the toolbar whenever any filter is active (A4), so a
 *     persisted filter is never an invisible state
 *
 * Each view calls TaskFilters.create({ ... }) with:
 *   mount       Element  — toolbar/root the Filter button is appended into
 *   getItems    () -> [] — current (unfiltered) items, read at apply-time
 *   features(item, ctx)  ->  { done, blocked, priorityHigh, overdue, dueSoon,
 *                              isMine, blocksOthers }
 *     ctx = { items, myUserId, today, soon, now }  (today/soon = YYYY-MM-DD)
 *   onApply(visible, meta) — view renders/hides from the matching subset
 *     meta = { state, activeCount, total, shown }
 *   hideDue     bool       — NEW: hide the "Due" group entirely (A1). Views
 *                            whose items have no due info (e.g. kanban matters
 *                            without dates) pass true so "Due" is not offered
 *                            when it cannot work.
 *
 * The component itself never touches DOM specific to a view.
 * ========================================================================== */
(function () {
  'use strict';

  var KEY = 'lf_task_filter';
  var DEFAULT = { show: 'all', priority: false, due: null, assignee: 'all',
                  type: '', from: '', to: '' };
  var FINISHED = { done: 1, closed: 1, completed: 1, archived: 1, resolved: 1 };

  function clone(o) {
    return { show: o.show, priority: !!o.priority, due: o.due, assignee: o.assignee,
             type: o.type || '', from: o.from || '', to: o.to || '' };
  }

  function normalize(o) {
    if (!o || typeof o !== 'object') return clone(DEFAULT);
    var s = clone(DEFAULT);
    if (o.show === 'open' || o.show === 'blocked' || o.show === 'done') s.show = o.show;
    if (o.priority) s.priority = true;
    if (o.due === 'overdue' || o.due === 'next7') s.due = o.due;
    if (o.assignee === 'mine') s.assignee = 'mine';
    /* calendar-only fields (task views never set them -> stay default/inert) */
    if (typeof o.type === 'string' && o.type !== '') s.type = o.type;
    if (typeof o.from === 'string' && o.from !== '') s.from = o.from;
    if (typeof o.to === 'string' && o.to !== '') s.to = o.to;
    return s;
  }

  function load(key) {
    try { return normalize(JSON.parse(localStorage.getItem(key || KEY))); }
    catch (e) { return clone(DEFAULT); }
  }
  function save(s, key) { try { localStorage.setItem(key || KEY, JSON.stringify(s)); } catch (e) {} }

  function activeCount(s) {
    return (s.show !== 'all' ? 1 : 0) + (s.priority ? 1 : 0) + (s.due ? 1 : 0) + (s.assignee === 'mine' ? 1 : 0)
      + (s.type !== '' ? 1 : 0) + (s.from !== '' ? 1 : 0) + (s.to !== '' ? 1 : 0);
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
    /* calendar extensions (inert for task views: state.type/from/to stay '') */
    if (s.type !== '' && f.type !== s.type) return false;
    if (s.from !== '' || s.to !== '') {
      var k = f.date || '';
      if (!k) return false;
      if (s.from !== '' && k < s.from) return false;
      if (s.to !== '' && k > s.to) return false;
    }
    return true;
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  /* A4 — always-visible active-filter banner ("Filters on — N — Showing X of Y — Clear").
     Rendered as a slim pill next to the toolbar; hidden when no filter is active. */
  function bannerHTML(state, total, shown) {
    var n = activeCount(state);
    if (!n) return '';
    return 'Filters on — <b>' + n + '</b> — Showing <b>' + shown + '</b> of <b>' + total + '</b>';
  }

  function create(options) {
    if (!options || typeof options.getItems !== 'function' ||
        typeof options.features !== 'function' || typeof options.onApply !== 'function') return null;

    var mount = options.mount || document.body;
    var storageKey = options.key || KEY;          /* calendar uses its own key */
    var state = load(storageKey);
    if (options.hideDue) state.due = null;   // A1: Due group is not offered — never carry a Due filter that cannot work
    /* calendar-only additions (all optional — the four task views pass none of these) */
    var showKeys = options.showChips || ['all', 'open', 'blocked', 'done'];
    var chipLabels = options.chipLabels || {};
    var typeChipsFn = (typeof options.typeChips === 'function') ? options.typeChips : null;
    var dateRange = !!options.dateRange;
    var hideAssignee = !!options.hideAssignee;
    var panelTitle = options.title || 'Filter tasks';
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

    /* Count, for every type chip, how many items it would show once chosen
       (removing the *type* filter but keeping every other active filter), so a
       chip that would yield 0 renders a visible disabled hint "(0)". */
    function countByType() {
      if (!typeChipsFn || !typeGroup) return {};
      var items = options.getItems() || [];
      var now = new Date();
      var today = dstr(now);
      var soon = dstr(new Date(now.getTime() + 7 * 86400000));
      var choices = typeChipsFn(items);
      var byKey = {};
      items.forEach(function (it) {
        var f = options.features(it, { items: items, myUserId: myUserId, today: today, soon: soon, now: now }) || {};
        choices.forEach(function (ch) {
          if (byKey[ch.key] === undefined) byKey[ch.key] = 0;
          var tmp = clone(state); tmp.type = ch.key;
          if (matches(tmp, f, today, soon)) byKey[ch.key]++;
        });
      });
      return byKey;
    }

    /* Rebuild the dynamic type-chip group (labels + live "(N)" counts). */
    function renderTypeChips() {
      if (!typeChipsFn || !typeGroup) return;
      while (typeGroup.firstChild) typeGroup.removeChild(typeGroup.firstChild);
      var items = options.getItems() || [];
      var choices = typeChipsFn(items);
      var counts = countByType();
      choices.forEach(function (ch) {
        var n = counts[ch.key] === undefined ? 0 : counts[ch.key];
        var c = el('button', 'lf-chip' + (n === 0 && state.type !== ch.key ? ' lf-chip--empty' : ''), ch.label);
        c.type = 'button';
        c.setAttribute('aria-pressed', state.type === ch.key ? 'true' : 'false');
        if (n === 0 && state.type !== ch.key) c.setAttribute('disabled', '');
        var ct = el('span', 'lf-chip-count', '(' + n + ')');
        ct.setAttribute('aria-hidden', 'true');
        c.appendChild(ct);
        c.addEventListener('click', function () { state.type = (state.type === ch.key) ? '' : ch.key; sync(); });
        typeGroup.appendChild(c);
      });
    }

    function apply() {
      save(state, storageKey);
      updateBadge();
      renderTypeChips();   /* calendar: keep live per-type counts next to each chip */
      var visible = compute();
      var total = (options.getItems() || []).length;
      var meta = { state: clone(state), activeCount: activeCount(state), total: total, shown: visible.length };
      options.onApply(visible, meta);
      updateBanner(meta);
    }

    function updateBanner(meta) {
      if (!banner) return;
      if (meta.activeCount > 0) {
        banner.style.display = 'inline-flex';
        banner.innerHTML = bannerHTML(meta.state, typeof meta.total === 'number' ? meta.total : 0, typeof meta.shown === 'number' ? meta.shown : 0)
          + ' <button type="button" class="lf-banner-clear" aria-label="Clear filters">Clear</button>';
      } else {
        banner.style.display = 'none';
      }
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
      /* calendar-only controls */
      if (dateFrom && String(dateFrom.value) !== String(state.from)) dateFrom.value = state.from || '';
      if (dateTo && String(dateTo.value) !== String(state.to)) dateTo.value = state.to || '';
      apply();
    }

    /* ── Build the UI ─────────────────────────────────────────────────── */
    var root = el('div', 'lf-filter');
    var hideDue = !!(options.hideDue);

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
    panel.setAttribute('aria-label', panelTitle);

    var head = el('div', 'lf-filter-head');
    head.appendChild(el('span', null, panelTitle));
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

    /* dynamic Event-type chips group (calendar only) — built from the REAL
       types present in the loaded items each apply, with live "(N)" counts */
    var typeGroup = null;
    if (typeChipsFn) {
      var typeG = group((options.typeLabel) || 'Event type');
      typeGroup = typeG.chips;
      panel.appendChild(typeG.wrap);
    }

    var showG = group('Show');
    var showChips = {};
    var SHOW_LABELS = { all: 'All', open: 'Open', blocked: 'Blocked', done: 'Done' };
    showKeys.forEach(function (k) {
      var c = chip(chipLabels[k] || SHOW_LABELS[k], state.show === k);
      c.addEventListener('click', function () { state.show = k; sync(); });
      showChips[k] = c; showG.chips.appendChild(c);
    });
    panel.appendChild(showG.wrap);

    var priG = group('Priority');
    var priChip = chip('Most critical', !!state.priority);
    priChip.addEventListener('click', function () { state.priority = !state.priority; sync(); });
    priG.chips.appendChild(priChip);
    panel.appendChild(priG.wrap);

    var dueG = group('Due');
    var dueChips = {};
    if (!hideDue) {
      ['overdue', 'next7'].forEach(function (k) {
        var c = chip({ overdue: 'Overdue', next7: 'Next 7 days' }[k], state.due === k);
        c.addEventListener('click', function () { state.due = (state.due === k) ? null : k; sync(); });
        dueChips[k] = c; dueG.chips.appendChild(c);
      });
      dueG.wrap.classList.add('lf-group-due');
      panel.appendChild(dueG.wrap);
    }

    /* calendar date range (From / To) — applies instantly on change */
    var dateFrom = null, dateTo = null;
    if (dateRange) {
      var dateG = group('Date range');
      function dateInput(cls, val) {
        var inp = el('input', cls);
        inp.type = 'date';
        inp.setAttribute('aria-label', cls.indexOf('lf-date-to') >= 0 ? 'To date' : 'From date');
        inp.value = val || '';
        return inp;
      }
      var dates = el('div', 'lf-dates');
      dateFrom = dateInput('lf-date-input lf-date-from', state.from || '');
      dateTo = dateInput('lf-date-input lf-date-to', state.to || '');
      dateFrom.addEventListener('change', function () { state.from = dateFrom.value || ''; sync(); });
      dateTo.addEventListener('change', function () { state.to = dateTo.value || ''; sync(); });
      dates.appendChild(dateFrom);
      dates.appendChild(el('span', 'lf-date-sep', '—'));
      dates.appendChild(dateTo);
      var clearDates = el('button', 'lf-filter-clear lf-date-clear', 'Clear');
      clearDates.type = 'button';
      clearDates.addEventListener('click', function () { state.from = ''; state.to = ''; sync(); });
      dates.appendChild(clearDates);
      dateG.chips.appendChild(dates);
      panel.appendChild(dateG.wrap);
    }

    if (!hideAssignee) {
      var asgG = group('Assignee');
      var asgChips = {};
      ['all', 'mine'].forEach(function (k) {
        var c = chip({ all: 'All', mine: 'Mine' }[k], state.assignee === k);
        c.addEventListener('click', function () { state.assignee = k; sync(); });
        asgChips[k] = c; asgG.chips.appendChild(c);
      });
      panel.appendChild(asgG.wrap);
    }

    /* A4 — always-visible active-filter banner (slim pill next to the toolbar) */
    var banner = el('div', 'lf-banner');
    banner.setAttribute('role', 'status');
    banner.setAttribute('aria-live', 'polite');
    banner.style.display = 'none';

    /* ── Interaction ─────────────────────────────────────────────────── */
    function doClear() { state = clone(DEFAULT); save(state, storageKey); sync(); }
    function toggle() { open = !open; panel.classList.toggle('open', open); updateBadge(); }
    function close() { open = false; panel.classList.remove('open'); updateBadge(); }

    btn.addEventListener('click', function (ev) { ev.stopPropagation(); toggle(); });
    clearBtn.addEventListener('click', function () { doClear(); });
    banner.addEventListener('click', function (ev) {
      if (ev.target && ev.target.classList && ev.target.classList.contains('lf-banner-clear')) doClear();
    });
    document.addEventListener('click', function (e) { if (open && !root.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && open) { e.stopPropagation(); close(); btn.focus(); }
    });

    btn.setAttribute('aria-controls', panel.id);
    root.appendChild(btn);
    root.appendChild(panel);
    root.appendChild(banner);
    mount.appendChild(root);

    updateBadge();
    ensureMe();   // warm the "Mine" identity so it's ready on first use

    return {
      getState: function () { return clone(state); },
      refresh: refresh,
      apply: apply,
      close: close,
      activeCount: function () { return activeCount(state); },
      /* A4 — programmatic clear (used by the banner Clear and by logout/login reset) */
      reset: doClear
    };
  }

  window.TaskFilters = {
    create: create,
    FINISHED: FINISHED,
    DEFAULT: clone(DEFAULT),
    KEY: KEY,
    inFinished: inFinished,
    /* pure predicate — exposed for headless JS-level tests (no server/browser needed) */
    matchesState: matches,
    /* A4 — wipe the persisted filter (call on login & logout so the next
       session never inherits a stale filter a user mistook for lost data). */
    resetStorage: function () { try { localStorage.removeItem(KEY); } catch (e) {} }
  };
})();
