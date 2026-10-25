(function () {
  function token() { try { return localStorage.getItem('jwt') || ''; } catch (e) { return ''; } }
  function request(path, options) {
    options = options || {};
    options.headers = options.headers || {};
    options.headers['Accept'] = 'application/json';
    options.headers['Authorization'] = 'Bearer ' + token();
    if (options.json !== undefined) {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.json);
      delete options.json;
    }
    return fetch(path, options).then(function (r) {
      return r.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = { raw: text }; }
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }
  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }
  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }
  function fmt(v) { return v == null ? '—' : String(v); }
  function runBadge(status) {
    var cls = 'badge';
    if (status === 'pending_approval') cls += ' warn';
    else if (status === 'error' || status === 'rejected') cls += ' error';
    else if (status === 'completed' || status === 'executed') cls += ' success';
    return { className: cls, label: status || 'unknown' };
  }

  async function loadRuns() {
    if (!token()) {
      clear(document.getElementById('agentRuns'));
      clear(document.getElementById('agentPending'));
      clear(document.getElementById('agentAudit'));
      document.getElementById('agentRunCount').textContent = '0';
      document.getElementById('agentPendingCount').textContent = '0';
      document.getElementById('agentAuditCount').textContent = '0';
      var msg = el('div', 'empty', 'Sign in with a superadmin JWT to use the in-app agent.');
      document.getElementById('agentRuns').appendChild(msg);
      document.getElementById('agentPending').appendChild(el('div', 'empty', 'No session token found.'));
      document.getElementById('agentAudit').appendChild(el('div', 'empty', 'No session token found.'));
      return;
    }
    var res = await request('/api/agent/runs?per_page=10');
    if (!res.ok) {
      document.getElementById('agentRuns').innerHTML = '';
      document.getElementById('agentRuns').appendChild(el('div', 'empty', 'Could not load runs (' + res.status + ').'));
      return;
    }
    var runs = (res.data && res.data.items) || [];
    document.getElementById('agentRunCount').textContent = String(runs.length);
    var runsBox = document.getElementById('agentRuns');
    var pendingBox = document.getElementById('agentPending');
    var auditBox = document.getElementById('agentAudit');
    clear(runsBox); clear(pendingBox); clear(auditBox);
    if (!runs.length) runsBox.appendChild(el('div', 'empty', 'No runs yet.'));
    var pending = [];
    var audits = [];
    runs.forEach(function (run) {
      var card = el('section', 'run-card');
      var head = el('div', 'meta', 'Run #' + run.id + ' · ' + fmt(run.created_at));
      var title = el('h3', '', run.goal || '');
      var badge = runBadge(run.status);
      card.appendChild(head);
      card.appendChild(title);
      card.appendChild(el('div', badge.className, badge.label));
      if (run.final_text) card.appendChild(el('pre', '', run.final_text));
      runsBox.appendChild(card);
      (run.pending_actions || []).forEach(function (action) { pending.push({ run: run, action: action }); });
      (run.steps || []).forEach(function (step) { audits.push({ run: run, step: step }); });
    });
    document.getElementById('agentPendingCount').textContent = String(pending.length);
    document.getElementById('agentAuditCount').textContent = String(audits.length);
    if (!pending.length) pendingBox.appendChild(el('div', 'empty', 'No pending approvals.'));
    pending.forEach(function (item) {
      var action = item.action;
      var card = el('section', 'approval-card');
      card.appendChild(el('div', 'meta', 'Action #' + action.id + ' · Run #' + item.run.id));
      card.appendChild(el('h3', '', action.tool));
      card.appendChild(el('div', action.status === 'pending' ? 'badge warn' : 'badge', action.status));
      var pre = el('pre', '', JSON.stringify(action.args || {}, null, 2));
      card.appendChild(pre);
      var actions = el('div', 'approval-actions');
      var approve = el('button', 'button', 'Approve');
      var reject = el('button', 'button button-secondary', 'Reject');
      approve.addEventListener('click', function () { mutateAction(action.id, 'approve'); });
      reject.addEventListener('click', function () { mutateAction(action.id, 'reject'); });
      actions.appendChild(approve); actions.appendChild(reject);
      card.appendChild(actions);
      pendingBox.appendChild(card);
    });
    if (!audits.length) auditBox.appendChild(el('div', 'empty', 'No audit rows yet.'));
    audits.forEach(function (item) {
      var step = item.step;
      var card = el('section', 'audit-card');
      card.appendChild(el('div', 'meta', 'Run #' + item.run.id + ' · step ' + step.step_no + ' · ' + step.kind));
      var head = step.tool ? step.tool : step.kind;
      card.appendChild(el('h3', '', head));
      card.appendChild(el('div', step.status === 'error' ? 'badge error' : 'badge', step.status));
      if (step.result_summary) card.appendChild(el('pre', '', step.result_summary));
      auditBox.appendChild(card);
    });
  }

  async function mutateAction(actionId, verb) {
    var res = await request('/api/agent/actions/' + encodeURIComponent(actionId) + '/' + verb, { method: 'POST' });
    if (!res.ok) {
      alert((res.data && res.data.error) || ('Action ' + verb + ' failed'));
      return;
    }
    await loadRuns();
  }

  async function submitGoal(goal) {
    var res = await request('/api/agent/runs', { method: 'POST', json: { goal: goal } });
    if (!res.ok) {
      alert((res.data && res.data.error) || ('Run failed (' + res.status + ')'));
      return;
    }
    document.getElementById('agentGoal').value = '';
    await loadRuns();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('agentGoalForm');
    var refresh = document.getElementById('agentRefresh');
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      submitGoal(document.getElementById('agentGoal').value.trim());
    });
    refresh.addEventListener('click', loadRuns);
    loadRuns();
    setInterval(loadRuns, 15000);
  });
})();
