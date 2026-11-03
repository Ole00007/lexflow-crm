/* ============================================================================
   LexFlow CRM — Matter-stage checklist (WS-K, feat/wave2-checklist)

   Page controller. The JWT lives in localStorage (key 'jwt'); every request
   carries it as a Bearer token, so all authorization is enforced server-side.
   All dynamic text is written with textContent (never innerHTML) to prevent
   XSS; element ids are quoted in handlers via dataset lookups.
   No libraries, no CDN (production CSP is script-src 'self').
   ============================================================================ */
(function () {
  'use strict';

  var ROOT = document.querySelector('.checklist-page');
  if (!ROOT) return;
  var CASE_ID = parseInt(ROOT.getAttribute('data-case-id'), 10);
  var STATUSES = ['todo', 'in_progress', 'done', 'blocked', 'not_applicable'];
  var STATUS_LABEL = {
    todo: 'To do', in_progress: 'In progress', done: 'Done',
    blocked: 'Blocked', not_applicable: 'N/A'
  };
  var RESOLVED = { done: 1, not_applicable: 1 };

  function token() {
    try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; }
  }
  function authHeaders(extra) {
    var h = { 'Authorization': 'Bearer ' + token() };
    if (extra) { for (var k in extra) h[k] = extra[k]; }
    return h;
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function show(id, on) {
    var e = document.getElementById(id);
    if (e) e.hidden = !on;
  }

  // ── data ──────────────────────────────────────────────────────────────────
  function api(method, url, body) {
    var opts = { method: method, headers: authHeaders(body ? { 'Content-Type': 'application/json' } : null) };
    if (body) opts.body = JSON.stringify(body);
    return fetch(url, opts);
  }

  function load() {
    show('cl-loading', true); show('cl-error', false); show('cl-denied', false);
    if (!token()) { show('cl-loading', false); show('cl-denied', true); return; }
    api('GET', '/api/cases/' + CASE_ID + '/checklist')
      .then(function (r) {
        if (r.status === 401 || r.status === 422) { show('cl-loading', false); show('cl-denied', true); return null; }
        if (!r.ok) throw new Error('status ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        show('cl-loading', false);
        render(data);
      })
      .catch(function () { show('cl-loading', false); show('cl-error', true); });
  }

  // ── render ──────────────────────────────────────────────────────────────────
  function render(data) {
    // header
    document.getElementById('cl-caseno').textContent = data.case_no ? ('· ' + data.case_no) : '';
    document.getElementById('cl-disclaimer').textContent = data.disclaimer || '';
    var pct = data.progress || 0;
    var ring = document.getElementById('cl-ring');
    ring.style.setProperty('--pct', pct);
    document.getElementById('cl-ring-pct').textContent = pct + '%';

    var total = (data.counts && data.counts.total) || 0;

    // empty -> offer init (server rejects non-admins with 403, which we surface)
    if (!total) {
      renderInit();
      document.getElementById('cl-stages').textContent = '';
      document.getElementById('cl-stepper').textContent = '';
      show('cl-next', false);
      return;
    }
    show('cl-init', false);

    // next-missing banner
    var nextWrap = document.getElementById('cl-next');
    if (data.next_missing) {
      document.getElementById('cl-next-item').textContent =
        (data.next_missing.label || '') +
        (data.next_missing.due_date ? ('  ·  due ' + data.next_missing.due_date) : '');
      nextWrap.hidden = false;
    } else {
      nextWrap.hidden = true;
    }

    renderStepper(data.stages, data.current_stage);
    renderStages(data.stages);
  }

  function renderInit() {
    var panel = document.getElementById('cl-init');
    panel.hidden = false;
    var sel = document.getElementById('cl-template');
    if (sel.dataset.loaded) return;
    api('GET', '/api/checklist/templates').then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (data) {
      if (!data) return;
      sel.textContent = '';
      (data.templates || []).forEach(function (t) {
        var o = el('option', null, t.label);
        o.value = t.key;
        sel.appendChild(o);
      });
      sel.dataset.loaded = '1';
    });
    document.getElementById('cl-init-btn').onclick = function () {
      var key = sel.value;
      if (!key) return;
      api('POST', '/api/cases/' + CASE_ID + '/checklist/init', { template: key })
        .then(function (r) {
          if (r.status === 403) { alert('Only an administrator can initialise a checklist.'); return; }
          if (r.ok) load();
        });
    };
  }

  function renderStepper(stages, currentStage) {
    var ol = document.getElementById('cl-stepper');
    ol.textContent = '';
    (stages || []).forEach(function (st) {
      var li = el('li', 'cl-step');
      if (st.state === 'done') li.classList.add('is-done');
      if (st.state === 'current') li.classList.add('is-current');
      li.appendChild(el('span', 'cl-step-dot'));
      li.appendChild(el('span', null, st.name));
      ol.appendChild(li);
    });
  }

  function renderStages(stages) {
    var host = document.getElementById('cl-stages');
    host.textContent = '';
    (stages || []).forEach(function (st) {
      var card = el('div', 'cl-stage');
      if (st.state === 'current') card.classList.add('is-current');
      if (st.state === 'done') card.classList.add('is-done');

      var head = el('div', 'cl-stage-head');
      head.appendChild(el('span', null, st.name));
      head.appendChild(el('span', 'cl-stage-tag', st.state));
      card.appendChild(head);

      (st.items || []).forEach(function (it) { card.appendChild(renderItem(it)); });
      host.appendChild(card);
    });
  }

  function renderItem(it) {
    var row = el('div', 'cl-item');
    if (RESOLVED[it.status]) row.classList.add('is-resolved');
    row.dataset.itemId = String(it.id);

    // status select
    var statusCell = el('div');
    var sel = el('select', 'cl-status');
    STATUSES.forEach(function (s) {
      var o = el('option', null, STATUS_LABEL[s]);
      o.value = s;
      if (s === it.status) o.selected = true;
      sel.appendChild(o);
    });
    sel.onchange = function () { patchStatus(it.id, sel.value, row); };
    statusCell.appendChild(sel);
    row.appendChild(statusCell);

    // label + sub
    var mid = el('div');
    mid.appendChild(el('span', 'cl-item-label', it.label));
    if (it.required_doc) mid.appendChild(el('span', 'cl-item-sub', '📄 ' + it.required_doc));
    if (it.status === 'blocked' && it.blocked_reason) {
      mid.appendChild(el('span', 'cl-item-sub cl-blocked', '⛔ ' + it.blocked_reason));
    }
    row.appendChild(mid);

    // meta: kind, owner chip, due, docs link, materialize, flag lawyer
    var meta = el('div', 'cl-item-meta');
    meta.appendChild(el('span', 'cl-kind', it.kind || ''));

    if (it.owner_role && it.owner_role_label) {
      var chip = el('span', 'cl-owner', it.owner_role_label);
      if (it.owner_role_color) chip.style.background = it.owner_role_color;
      meta.appendChild(chip);
    }
    if (it.due_date) {
      var due = el('span', 'cl-due', 'due ' + it.due_date);
      if (isOverdue(it.due_date) && !RESOLVED[it.status]) due.classList.add('is-overdue');
      meta.appendChild(due);
    }
    // vault docs link (superadmin only — key present only then)
    if (it.vault_docs_api) {
      var a = el('a', 'cl-vaultlink', 'Open in vault');
      a.href = it.vault_docs_api;
      a.target = '_blank'; a.rel = 'noopener';
      meta.appendChild(a);
    }
    // materialize button
    var matBtn = el('button', 'cl-actbtn', it.task_id ? 'On Gantt ✓' : 'Materialize as task');
    matBtn.type = 'button';
    matBtn.disabled = !!it.task_id;
    matBtn.onclick = function () { materialize(it.id); };
    meta.appendChild(matBtn);

    // flag lawyer button
    var flagBtn = el('button', 'cl-actbtn', 'Flag lawyer');
    flagBtn.type = 'button';
    flagBtn.onclick = function () { flagLawyer(it); };
    meta.appendChild(flagBtn);

    row.appendChild(meta);
    return row;
  }

  function isOverdue(iso) {
    try {
      var d = new Date(iso + 'T00:00:00');
      var today = new Date(); today.setHours(0, 0, 0, 0);
      return d < today;
    } catch (e) { return false; }
  }

  // ── actions ────────────────────────────────────────────────────────────────
  function patchStatus(itemId, status, row) {
    var body = { status: status };
    if (status === 'blocked') {
      var reason = prompt('Reason this item is blocked (optional):') || '';
      if (reason) body.blocked_reason = reason.slice(0, 300);
    }
    api('PATCH', '/api/checklist/items/' + itemId, body).then(function (r) {
      if (r.ok) { load(); } else { alert('Could not update status.'); load(); }
    });
  }

  function materialize(itemId) {
    api('POST', '/api/checklist/items/' + itemId + '/materialize', {}).then(function (r) {
      if (r.ok) { load(); } else { alert('Could not materialize as task.'); }
    });
  }

  function flagLawyer(it) {
    if (!it.task_id) {
      if (confirm('This item is not yet on the Gantt. Materialize it as a task first, then flag the lawyer?')) {
        api('POST', '/api/checklist/items/' + it.id + '/materialize', {}).then(function (r) {
          if (r.ok) r.json().then(function (d) { doFlag(d.task_id); });
          else alert('Could not materialize as task.');
        });
      }
      return;
    }
    doFlag(it.task_id);
  }

  function doFlag(taskId) {
    if (!taskId) return;
    var reason = prompt('Reason for flagging the lawyer (optional):') || '';
    api('POST', '/api/gantt/tasks/' + taskId + '/flag-lawyer', { reason: reason.slice(0, 500) })
      .then(function (r) {
        if (r.ok) alert('Lawyer flagged.'); else alert('Could not flag the lawyer.');
      });
  }

  load();
})();
