(function () {
  'use strict';
  var bubble = document.getElementById('eliza-bubble'), panel = document.getElementById('eliza-panel');
  if (!bubble || !panel) return;
  try { if (!localStorage.getItem('jwt')) { bubble.style.display = 'none'; return; } } catch (e) {}
  var msgs = document.getElementById('eliza-msgs'), form = document.getElementById('eliza-form'), input = document.getElementById('eliza-input');
  var KEY = 'eliza-history-v1', hist = [], busy = false;

  function token() { try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; } }
  function api(path, body) {
    return fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', 'Authorization': 'Bearer ' + token() }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, status: r.status, data: d }; }); });
  }
  function save() { try { sessionStorage.setItem(KEY, JSON.stringify(hist.slice(-40))); } catch (e) {} }
  function add(text, cls, noSave) {
    var d = document.createElement('div'); d.className = 'eliza-msg ' + cls; d.textContent = text; msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight; if (!noSave) { hist.push({ t: text, c: cls }); save(); } return d;
  }
  function card(action) {
    var c = document.createElement('div'); c.className = 'eliza-card';
    var p = document.createElement('div'); p.textContent = action.description || action.tool; c.appendChild(p);
    var row = document.createElement('div'); row.className = 'row';
    var ok = document.createElement('button'); ok.className = 'ok'; ok.textContent = 'Confirm';
    var no = document.createElement('button'); no.textContent = 'Cancel';
    function resolve(verb) {
      ok.disabled = no.disabled = true;
      api('/api/agent/chat/actions/' + action.id + '/' + verb).then(function (r) {
        c.classList.add('done'); row.remove(); bubble.classList.remove('has-pending');
        add(r.data.reply || (r.ok ? 'Done.' : 'Something went wrong.'), r.ok ? 'bot' : 'bot err');
        if (r.ok && verb === 'approve') document.dispatchEvent(new CustomEvent('eliza:changed'));
      });
    }
    ok.onclick = function () { resolve('approve'); }; no.onclick = function () { resolve('reject'); };
    row.appendChild(ok); row.appendChild(no); c.appendChild(row); msgs.appendChild(c); msgs.scrollTop = msgs.scrollHeight;
    bubble.classList.add('has-pending');
  }
  function send(text) {
    text = (text || '').trim(); if (!text || busy) return;
    if (!token()) { add('Please sign in again — your session has expired.', 'bot err'); return; }
    busy = true; add(text, 'user'); var typing = add('…', 'bot', true);
    api('/api/agent/chat', { message: text }).then(function (r) {
      typing.remove(); busy = false;
      if (!r.ok) { add(r.status === 404 ? 'Eliza is not enabled on this workspace.' : (r.data.error || 'Something went wrong.'), 'bot err'); return; }
      add(r.data.reply, 'bot'); if (r.data.pending_action) card(r.data.pending_action);
    }).catch(function () { typing.remove(); busy = false; add('Network error. Try again.', 'bot err'); });
  }
  function chips() {
    var w = document.createElement('div'); w.className = 'eliza-chips';
    ['Show my open tasks', "What's on my agenda?", 'Create task … for matter …', 'Schedule hearing … on 2026-11-12 at 10:30'].forEach(function (t) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = t;
      b.onclick = function () { if (t.indexOf('…') > -1) { input.value = t.replace(/…/g, '').replace(/\s+/g, ' ').trim() + ' '; input.focus(); } else send(t); };
      w.appendChild(b);
    }); msgs.appendChild(w);
  }
  function boot() {
    try { hist = JSON.parse(sessionStorage.getItem(KEY) || '[]'); } catch (e) { hist = []; }
    if (hist.length) hist.forEach(function (m) { add(m.t, m.c, true); });
    else { add("Hi, I'm Eliza. I help you with your matters, documents, tasks and agenda. I always ask before changing anything.", 'bot'); }
    chips();
  }
  function toggle(open) {
    var on = open === undefined ? !panel.classList.contains('open') : open;
    panel.classList.toggle('open', on); if (on) { input.focus(); msgs.scrollTop = msgs.scrollHeight; }
  }
  bubble.onclick = function () { toggle(); };
  document.getElementById('eliza-close').onclick = function () { toggle(false); };
  form.onsubmit = function (e) { e.preventDefault(); var v = input.value; input.value = ''; send(v); };
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') toggle(false); });
  boot();
})();
