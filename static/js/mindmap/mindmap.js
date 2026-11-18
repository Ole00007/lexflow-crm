/* Mindmap — human note stream + agent draft tray.
 * Auth: JWT in localStorage['jwt'] as Bearer (same contract as gantt_view.js).
 * Notes:  GET /api/notes/ , POST /api/notes/
 * Drafts: GET /api/agent/drafts?status=proposed , POST /api/agent/drafts/<id>/accept|reject
 * No send/email controls. No "approve all". Agent (promoted) notes labelled "for review".
 * Demo mode: when window.MM_FIXTURES is present (static preview page), all I/O is
 * served from that in-memory store — no network, no auth. UI logic is identical.
 */
(function () {
  'use strict';

  var page = document.getElementById('mm-page');
  if (!page) return;

  var DEMO = !!(window.MM_FIXTURES && window.MM_FIXTURES.notes);
  var store = DEMO ? clone(window.MM_FIXTURES) : null;

  function nextId() {
    if (!store._next) store._next = 100;
    return store._next++;
  }

  var wsId = parseInt(page.getAttribute('data-ws-id') || '', 10) || null;
  var tabButtons = Array.prototype.slice.call(page.querySelectorAll('.mm-tab'));
  var streamList = document.getElementById('mm-stream-list');
  var tray = document.getElementById('mm-tray');
  var trayList = document.getElementById('mm-tray-list');
  var composer = document.getElementById('mm-post');
  var composeBox = document.getElementById('mm-compose');
  var postFeedback = document.getElementById('mm-post-feedback');
  var applyBtn = document.getElementById('mm-apply');
  var filters = {
    source: document.getElementById('mm-source'),
    author: document.getElementById('mm-author'),
    dateFrom: document.getElementById('mm-date-from'),
    dateTo: document.getElementById('mm-date-to'),
    q: document.getElementById('mm-q')
  };

  var TARGET_LABEL = { workspace: 'Workspace', task: 'Task', case: 'Case', contact: 'Contact' };
  var ORIGIN_LABEL = { human_request: 'Human request', superior_agent: 'Superior agent', event_rule: 'Event rule' };
  var NO_TARGET_HINT = 'Select a Task, Case or Contact to post a note for it.';
  var ACTIVE = { target_type: 'workspace', target_id: wsId };
  var loadingDrafts = false;

  /* ---------- low-level I/O ---------- */

  function token() { try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; } }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  function qs(params) {
    var parts = [];
    Object.keys(params).forEach(function (k) {
      var v = params[k];
      if (v === '' || v === null || v === undefined) return;
      parts.push(encodeURIComponent(k) + '=' + encodeURIComponent(v));
    });
    return parts.length ? '?' + parts.join('&') : '';
  }

  function call(url, options) {
    options = options || {};
    var t = token();
    return fetch(url, {
      method: options.method || 'GET',
      headers: {
        'Authorization': 'Bearer ' + t,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
      },
      credentials: 'same-origin',
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  /* Demo-mode I/O (static preview): serve from store, mutate in memory. */
  function demoCall(path, options) {
    var m;
    if ((m = path.match(/^\/api\/notes\//))) {
      if (!options || options.method !== 'POST') {
        // Apply the same query filters the real GET /api/notes applies.
        var entries = path.replace(/^[^?]*/, '').replace(/^\?/, '').split('&');
        var f = {};
        entries.forEach(function (pair) {
          var kv = pair.split('=');
          if (kv[0]) f[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
        });
        var list = store.notes.slice();
        if (f.source) list = list.filter(function (n) { return n.source === f.source; });
        if (f.target_type) list = list.filter(function (n) { return n.target_type === f.target_type; });
        if (f.author_id) {
          var aid = String(f.author_id);
          list = list.filter(function (n) { return String(n.author_id) === aid; });
        }
        if (f.q) {
          var qq = f.q.toLowerCase();
          list = list.filter(function (n) {
            return (n.content || '').toLowerCase().indexOf(qq) > -1
                || (n.author_name || '').toLowerCase().indexOf(qq) > -1;
          });
        }
        return Promise.resolve({ ok: true, status: 200, data: list });
      }
      var note = {
        id: nextId(),
        author_id: null, author_email: 'demo@lexflow', author_name: 'Demo user',
        target_type: ACTIVE.target_type, target_id: ACTIVE.target_id,
        content: (options.body && options.body.content) || '',
        source: 'human', source_ref: null,
        created_at: new Date().toISOString(), updated_at: new Date().toISOString()
      };
      store.notes = [note].concat(store.notes);
      return Promise.resolve({ ok: true, status: 201, data: note });
    }
    if ((m = path.match(/^\/api\/agent\/drafts(?:\?.*)?$/))) {
      return Promise.resolve({ ok: true, status: 200, data: store.drafts.filter(function (d) { return d.status === 'proposed'; }) });
    }
    if ((m = path.match(/^\/api\/agent\/drafts\/(\d+)\/(accept|reject)$/))) {
      var id = parseInt(m[1], 10);
      var action = m[2];
      var draft = store.drafts.find(function (d) { return d.id === id; });
      if (!draft) return Promise.resolve({ ok: false, status: 404, data: { error: 'not found' } });
      if (draft.status !== 'proposed' || (draft.expires_at && new Date(draft.expires_at) <= new Date())) {
        return Promise.resolve({ ok: false, status: 409, data: { error: 'already resolved' } });
      }
      if (action === 'accept') {
        draft.status = 'accepted'; draft.note_id = nextId();
        store.notes = [{
          id: draft.note_id, author_id: draft.requested_by, author_email: 'elisa@lexflow',
          author_name: 'Elisa draft', target_type: draft.target_type, target_id: draft.target_id,
          content: draft.content, source: 'agent', source_ref: String(draft.id),
          created_at: new Date().toISOString(), updated_at: new Date().toISOString()
        }].concat(store.notes);
      } else {
        draft.status = 'rejected';
      }
      return Promise.resolve({ ok: true, status: 200, data: { draft: draft } });
    }
    return Promise.resolve({ ok: false, status: 404, data: {} });
  }

  function api(path, options) {
    return DEMO ? demoCall(path, options) : call(path, options);
  }

  /* ---------- rendering helpers ---------- */

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function relativeTime(iso) {
    if (!iso) return '';
    var then = new Date(iso);
    if (isNaN(then.getTime())) return '';
    var sec = Math.round((Date.now() - then.getTime()) / 1000);
    if (sec < 45) return 'just now';
    var min = Math.round(sec / 60);
    if (min < 60) return min + ' min ago';
    var hr = Math.round(min / 60);
    if (hr < 24) return hr + ' hr ago';
    var day = Math.round(hr / 24);
    if (day < 7) return day + ' day' + (day === 1 ? '' : 's') + ' ago';
    return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function countdown(iso) {
    if (!iso) return '';
    var then = new Date(iso);
    if (isNaN(then.getTime())) return '';
    var ms = then.getTime() - Date.now();
    if (ms <= 0) return 'expired';
    var hr = Math.floor(ms / 3600000);
    var min = Math.floor((ms % 3600000) / 60000);
    return 'expires in ' + hr + 'h ' + min + 'm';
  }

  function targetTag(n) {
    var label = TARGET_LABEL[n.target_type] || n.target_type;
    return label + ' #' + n.target_id;
  }

  function authorName(n) {
    if (n.author_name) return n.author_name;
    if (n.author_email) return n.author_email;
    return 'system';
  }

  function chipFor(n) {
    if (n.source === 'agent') {
      // Promoted agent draft: never a send/email action — labelled "for review".
      return '<span class="mm-chip mm-chip-draft">Elisa draft</span>'
        + '<span class="mm-chip mm-review">for review</span>';
    }
    return '<span class="mm-chip mm-human">Human</span>';
  }

  /* ---------- note stream ---------- */

  // Rebuild the Author filter's <select> from the loaded notes' distinct authors,
  // preserving the current selection so Apply/refresh keep the chosen filter.
  function populateAuthorSelect(notes) {
    if (!filters.author) return;
    var current = filters.author.value;
    var byId = {};
    (notes || []).forEach(function (n) {
      if (n.author_id === null || n.author_id === undefined) return;
      byId[String(n.author_id)] = authorName(n);
    });
    var ids = Object.keys(byId);
    var html = '<option value="">Any author</option>';
    ids.forEach(function (id) { html += '<option value="' + esc(id) + '">' + esc(byId[id]) + '</option>'; });
    filters.author.innerHTML = html;
    if (current && byId[current] !== undefined) filters.author.value = current;
  }

  // Inline, persistent composer feedback (fixes silent post failures): aria-live element
  // next to the Post button shows server errors/hints even when the draft tray is hidden.
  function setComposerFeedback(msg, kind) {
    if (!postFeedback) return;
    postFeedback.textContent = msg || '';
    postFeedback.className = 'mm-post-feedback mm-post-feedback-' + (kind || 'ok');
    if (msg) composer.setAttribute('aria-describedby', 'mm-post-feedback');
    else composer.removeAttribute('aria-describedby');
  }

  function updateComposerState() {
    var hasTarget = ACTIVE.target_id !== null && ACTIVE.target_id !== undefined && ACTIVE.target_id !== '';
    composer.disabled = !hasTarget;
    if (hasTarget) {
      composer.title = '';
      setComposerFeedback('', 'ok');
    } else {
      composer.title = NO_TARGET_HINT;
      setComposerFeedback(NO_TARGET_HINT, 'hint');
    }
  }

  function noteCard(n) {
    return '<article class="mm-card' + (n.source === 'agent' ? ' mm-agent' : '') + '">'
      + '<div class="mm-meta">'
      +   chipFor(n)
      +   '<span class="mm-author">' + esc(authorName(n)) + '</span>'
      +   '<span class="mm-time">' + esc(relativeTime(n.created_at)) + '</span>'
      +   '<span class="mm-target">' + esc(targetTag(n)) + '</span>'
      + '</div>'
      + '<div class="mm-content">' + esc(n.content) + '</div>'
      + '</article>';
  }

  function buildParams() {
    return {
      target_type: ACTIVE.target_type,
      target_id: ACTIVE.target_id,
      source: filters.source.value,
      author_id: filters.author.value,
      date_from: filters.dateFrom.value,
      date_to: filters.dateTo.value,
      q: filters.q.value.trim()
    };
  }

  function loadNotes() {
    var loading = document.createElement('div');
    loading.className = 'mm-state';
    loading.textContent = 'Loading notes…';
    streamList.appendChild(loading);
    return api('/api/notes/' + qs(buildParams())).then(function (res) {
      var notes = res.ok && Array.isArray(res.data) ? res.data : [];
      populateAuthorSelect(notes);
      if (!notes.length) {
        streamList.innerHTML = '<div class="mm-state">No notes yet for this target.</div>';
        return;
      }
      streamList.innerHTML = notes.map(noteCard).join('');
    }).catch(function () {
      streamList.innerHTML = '<div class="mm-state">Could not load notes. Check your connection.</div>';
    }).then(function () {
      if (loading.parentNode) loading.parentNode.removeChild(loading);
    });
  }

  function postNote() {
    var text = composeBox.value.trim();
    if (composer.disabled || ACTIVE.target_id === null || ACTIVE.target_id === undefined) {
      updateComposerState();
      return;
    }
    if (!text) { composeBox.focus(); return; }
    composer.disabled = true;
    api('/api/notes/', {
      method: 'POST',
      body: { target_type: ACTIVE.target_type, target_id: ACTIVE.target_id, content: text }
    }).then(function (res) {
      composer.disabled = false;
      if (res.ok) {
        composeBox.value = '';
        setComposerFeedback('Note posted.', 'ok');
        loadNotes();
      } else {
        setComposerFeedback((res.data && res.data.error) || 'Could not post note.', 'err');
      }
    }).catch(function () {
      composer.disabled = false;
      setComposerFeedback('Could not post note. Check your connection.', 'err');
    });
  }

  /* ---------- draft tray ---------- */

  function flashTray(msg, kind) {
    var n = document.createElement('div');
    n.className = 'mm-notice ' + (kind || '');
    n.textContent = msg;
    if (!trayList.firstChild) trayList.appendChild(n);
    else trayList.insertBefore(n, trayList.firstChild);
    setTimeout(function () { if (n.parentNode) n.parentNode.removeChild(n); }, 3500);
  }

  function loadDrafts() {
    if (loadingDrafts) return;
    loadingDrafts = true;
    var wasVisible = !tray.hidden;
    api('/api/agent/drafts' + qs({ status: 'proposed' })).then(function (res) {
      var drafts = res.ok && Array.isArray(res.data) ? res.data : [];
      renderTray(drafts, wasVisible);
    }).catch(function () {
      tray.setAttribute('hidden', '');
      trayList.innerHTML = '';
    }).then(function () { loadingDrafts = false; });
  }

  function draftCard(d) {
    var origin = ORIGIN_LABEL[d.origin] || d.origin;
    var ev = d.evidence ? '<div class="mm-evidence">' + esc(d.evidence) + '</div>' : '';
    return '<article class="mm-draft" data-id="' + d.id + '">'
      + '<div class="mm-draft-top">'
      +   '<span class="mm-origin ' + esc(d.origin || '') + '">' + esc(origin) + '</span>'
      +   '<span class="mm-draft-target">' + esc(targetTag(d)) + '</span>'
      + '</div>'
      + '<div class="mm-draft-content">' + esc(d.content) + '</div>'
      + ev
      + '<div class="mm-expiry">' + esc(countdown(d.expires_at)) + '</div>'
      + '<div class="mm-draft-actions">'
      +   '<button class="mm-accept" type="button" data-action="accept">Accept</button>'
      +   '<button class="mm-reject" type="button" data-action="reject">Reject</button>'
      + '</div>'
      + '</article>';
  }

  function renderTray(drafts, wasVisible) {
    if (!drafts.length) {
      if (wasVisible) {
        // A decision emptied a previously-shown tray — confirm with the empty state.
        tray.removeAttribute('hidden');
        trayList.innerHTML = '<div class="mm-tray-empty">No drafts waiting for review.</div>';
      } else {
        // No proposals yet: the tray is only visible when there is something to review.
        tray.setAttribute('hidden', '');
        trayList.innerHTML = '';
      }
      return;
    }
    tray.removeAttribute('hidden');
    trayList.innerHTML = drafts.map(draftCard).join('');
  }

  function decide(id, action) {
    api('/api/agent/drafts/' + id + '/' + action, { method: 'POST' }).then(function (res) {
      if (res.ok) {
        // Accept promotes a draft into the stream (server-side); refresh both.
        loadDrafts();
        loadNotes();
      } else if (res.status === 410) {
        flashTray('This draft has expired.', 'err');
        loadDrafts();
      } else if (res.status === 409) {
        flashTray('This draft was already resolved.', 'err');
        loadDrafts();
      } else {
        flashTray((res.data && res.data.error) || 'Action failed.', 'err');
      }
    }).catch(function () {
      flashTray('Action failed. Check your connection.', 'err');
    });
  }

  /* ---------- events ---------- */

  tabButtons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      tabButtons.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      ACTIVE.target_type = btn.getAttribute('data-target-type');
      var tid = btn.getAttribute('data-target-id');
      ACTIVE.target_id = tid ? parseInt(tid, 10) : null;
      updateComposerState();
      loadNotes();
    });
  });

  applyBtn.addEventListener('click', loadNotes);
  Object.keys(filters).forEach(function (k) {
    if (k === 'source' || k === 'q') {
      filters[k].addEventListener('change', loadNotes);
      if (k === 'q') filters[k].addEventListener('keydown', function (e) { if (e.key === 'Enter') loadNotes(); });
    }
  });

  composer.addEventListener('click', postNote);
  composeBox.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) postNote();
  });

  trayList.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('button[data-action]');
    if (!btn) return;
    var card = btn.closest('.mm-draft');
    if (!card) return;
    btn.disabled = true;
    decide(parseInt(card.getAttribute('data-id'), 10), btn.getAttribute('data-action'));
  });

  /* ---------- boot ---------- */
  var activeTab = tabButtons.filter(function (b) {
    return b.getAttribute('data-target-type') === ACTIVE.target_type;
  })[0];
  if (activeTab) activeTab.classList.add('active');
  updateComposerState();
  loadNotes();
  loadDrafts();
  // Keep the tray's expiry countdowns fresh.
  setInterval(loadDrafts, 60000);
})();
