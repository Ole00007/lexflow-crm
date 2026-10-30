/* ============================================================================
 * LexFlow — ROI "My progress" tracker (PART D).
 * static/js/roi/roi_progress.js
 *
 * Loaded only when ROI_TRACKER_ENABLED and NOT in embed mode. Uses the JWT from
 * localStorage to hit GET/PUT /api/roi/progress (tenant-scoped server-side).
 * Self-reported values, compared with the calculator's projection. Honest
 * wording throughout; no PII captured beyond the caller's own session.
 * ========================================================================== */
(function () {
  'use strict';

  var RC = window.ROICalculator;
  if (!RC) return;

  function $(id) { return document.getElementById(id); }
  function lang() { return document.body.getAttribute('data-lang') || 'it'; }
  function euros(n) { return RC.fmtEur(n); }

  var rows = [];
  var scope = 'own';

  // Read the current calculator inputs (the projection baseline).
  function readCalculator() {
    function v(id, fb) { var el = $(id); return el ? Number(el.value) : fb; }
    return {
      lawyers: v('in_lawyers', RC.DEFAULTS.lawyers),
      annualCost: v('in_cost', RC.DEFAULTS.annualCost),
      mattersPerMonth: v('in_matters', RC.DEFAULTS.mattersPerMonth),
      price: v('in_price', RC.DEFAULTS.price),
      hoursPerMatter: v('in_hmatter', RC.DEFAULTS.hoursPerMatter),
      billableHours: v('in_billable', RC.DEFAULTS.billableHours),
      ramp: (v('in_ramp', RC.DEFAULTS.ramp * 100)) / 100
    };
  }

  function authHeaders() {
    var t = null;
    try { t = localStorage.getItem('jwt'); } catch (e) { t = null; }
    var h = { 'Content-Type': 'application/json' };
    if (t) h['Authorization'] = 'Bearer ' + t;
    return h;
  }

  function statusHtml(msg) {
    var el = $('tp_status');
    if (el) el.textContent = msg;
  }

  /* Chart: projected (from calculator) vs actual (self-reported), per month,
     as cumulative euro values, with an ahead/behind line. */
  function drawChart(data) {
    var canvas = $('tp_chart');
    var caption = $('tp_chartcaption');
    if (!canvas || !caption || !data.length) {
      if (canvas && $('tp_chartwrap')) $('tp_chartwrap').style.display = 'none';
      return;
    }
    if (canvas) $('tp_chartwrap').style.display = '';
    var W = 620, H = 260, padL = 66, padR = 10, padT = 14, padB = 34;
    canvas.width = W; canvas.height = H;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    /* Ensure it renders even when lines are flat (all zeros) — floor at 1. */
    var projMax = Math.max.apply(null, data.map(function (d) { return Math.abs(d.cumProj); }));
    var actMax = Math.max.apply(null, data.map(function (d) { return Math.abs(d.cumAct); }));
    var vMax = Math.max(projMax, actMax, 1);
    var xKey = function (i) { return padL + i * ((W - padL - padR) / Math.max(data.length - 1, 1)); };
    var yKey = function (v) { return H - padB - (v / vMax) * (H - padT - padB); };

    ctx.clearRect(0, 0, W, H);
    ctx.font = '11px Inter, sans-serif';
    // grid + y labels
    ctx.fillStyle = '#9AA7BD';
    for (var g = 0; g <= 4; g++) {
      var gyVal = (vMax / 4) * g;
      var gy = H - padB - (gyVal / vMax) * (H - padT - padB);
      ctx.strokeStyle = '#2A3550'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(padL, gy); ctx.lineTo(W - padR, gy); ctx.stroke();
      ctx.fillText('€' + Math.round(gyVal), 4, gy + 4);
    }

    function line(key, color, getV) {
      ctx.strokeStyle = color; ctx.lineWidth = 2.4; ctx.beginPath();
      data.forEach(function (d, i) { var x = xKey(i); var y = yKey(getV(d)); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
      ctx.stroke();
    }
    function dots(key, color, getV) {
      ctx.fillStyle = color;
      data.forEach(function (d, i) { var x = xKey(i); var y = yKey(getV(d)); ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fill(); });
    }
    line('proj', '#E9C46A', function (d) { return d.cumProj; });
    dots('proj', '#E9C46A', function (d) { return d.cumProj; });
    line('act', '#66BB6A', function (d) { return d.cumAct; });
    dots('act', '#66BB6A', function (d) { return d.cumAct; });

    // x labels (month)
    ctx.fillStyle = '#9AA7BD'; ctx.textAlign = 'center';
    data.forEach(function (d, i) { ctx.fillText(d.month, xKey(i), H - 14); });
    ctx.textAlign = 'left';

    var l = lang();
    caption.textContent = l === 'en'
      ? 'Cumulative € — gold: projected (calculator), green: actual (self-reported).'
      : '€ cumulativi — oro: proiettati (calcolatore), verde: reali (auto-dichiarati).';
  }

  function euroForHours(hours) {
    var r = RC.computeRoi(readCalculator());
    return hours * r.hourlyValue;
  }

  /* Build the cumulative series: projected cumulative vs actual cumulative. */
  function buildSeries() {
    var r = RC.computeRoi(readCalculator());
    var projMonthly = r.valuePerMonth;
    var actualByMonth = {};
    rows.forEach(function (row) { actualByMonth[row.month] = euroForHours(row.hours_saved_actual); });

    var months = Object.keys(actualByMonth).sort();
    var cumP = 0, cumA = 0;
    var series = months.map(function (m) {
      cumP += projMonthly;
      cumA += (actualByMonth[m] || 0);
      return { month: m, cumProj: cumP, cumAct: cumA };
    });
    return series;
  }

  function renderTable() {
    var tbody = document.querySelector('#tp_table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    var noRows = !rows || !rows.length;

    var empty = $('tp_empty');
    if (empty) empty.hidden = !noRows;
    var chartWrap = $('tp_chartwrap');
    if (chartWrap && noRows) chartWrap.style.display = 'none';

    if (noRows) return;

    var sorted = rows.slice().sort(function (a, b) { return a.month.localeCompare(b.month); });
    var cumAct = 0, cumProj = 0;
    var projMonthly = RC.computeRoi(readCalculator()).valuePerMonth;

    sorted.forEach(function (row) {
      var actEur = euroForHours(row.hours_saved_actual);
      var projEur = projMonthly;
      cumAct += actEur; cumProj += projEur;
      var delta = cumAct - cumProj;
      var tr = document.createElement('tr');
      tr.innerHTML = '<td>' + row.month + '</td>' +
        '<td class="num">' + RC.fmtInt(row.hours_saved_actual) + ' h</td>' +
        '<td class="num">' + RC.fmtInt(row.matters_handled) + '</td>' +
        '<td class="num">' + euros(projEur) + '</td>' +
        '<td class="num">' + euros(actEur) + '</td>' +
        '<td class="num roi-track-delta ' + (delta >= 0 ? 'pos' : 'neg') + '">' +
        (delta >= 0 ? '+' : '') + euros(delta) + '</td>';
      tbody.appendChild(tr);
    });
    drawChart(buildSeries());
  }

  function load() {
    fetch('/api/roi/progress', { headers: authHeaders() })
      .then(function (res) {
        if (res.status === 401 || res.status === 403) { throw new Error('auth'); }
        return res.json();
      })
      .then(function (data) {
        rows = (data && data.rows) || [];
        scope = (data && data.scope) || 'own';
        renderTable();
        if (scope === 'workspace') {
          statusHtml(lang() === 'en'
            ? 'Showing the whole workspace total (admin view).'
            : 'Mostri il totale dello studio (vista amministratore).');
        }
      })
      .catch(function (e) {
        if (e && e.message === 'auth') {
          statusHtml(lang() === 'en'
            ? 'Please log in to the CRM to track your progress.'
            : 'Accedi alla CRM per tracciare i tuoi progressi.');
        } else {
          statusHtml('⚠ ' + (lang() === 'en' ? 'Could not load your progress.' : 'Impossibile caricare i progressi.'));
        }
      });
  }

  function save() {
    var month = ($('tp_month') ? $('tp_month').value : '');
    var hours = ($('tp_hours') ? Number($('tp_hours').value) : 0);
    var matters = ($('tp_matters') ? Math.round(Number($('tp_matters').value)) : 0);
    var note = ($('tp_note') ? $('tp_note').value : '');

    if (!/^\d{4}-\d{2}$/.test(month)) {
      statusHtml(lang() === 'en' ? 'Select a month first.' : 'Seleziona prima un mese.');
      return;
    }
    if (isNaN(hours) || hours < 0 || hours > 744) {
      statusHtml(lang() === 'en' ? 'Hours must be between 0 and 744.' : 'Le ore devono essere tra 0 e 744.');
      return;
    }
    if (isNaN(matters) || matters < 0) {
      statusHtml(lang() === 'en' ? 'Matters must be ≥ 0.' : 'Le pratiche devono essere ≥ 0.');
      return;
    }
    if (note.length > 200) { note = note.substring(0, 200); }

    var body = { month: month, hours_saved_actual: hours, matters_handled: matters, note: note };

    var el = $('tp_status');
    if (el) { el.className = 'roi-track-status'; el.textContent = lang() === 'en' ? 'Saving…' : 'Salvataggio…'; }

    fetch('/api/roi/progress', {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(body)
    })
      .then(function (res) {
        if (res.status === 401 || res.status === 403) throw new Error('auth');
        if (res.status === 400) return res.json().then(function (d) { throw new Error(d && d.error ? (d.error + ' ' + (d.details || []).join('; ')) : 'Validation'); });
        if (!res.ok) throw new Error('server');
        return res.json();
      })
      .then(function () {
        var el2 = $('tp_status');
        if (el2) { el2.className = 'roi-track-status ok'; el2.textContent = lang() === 'en' ? 'Saved. ✓' : 'Salvato. ✓'; }
        load();
      })
      .catch(function (e) {
        var el3 = $('tp_status');
        if (el3) { el3.className = 'roi-track-status err'; el3.textContent = (lang() === 'en' ? 'Error: ' : 'Errore: ') + (e && e.message); }
      });
  }

  function exportCsv() {
    if (!rows || !rows.length) {
      statusHtml(lang() === 'en' ? 'Nothing to export yet.' : 'Nessun dato da esportare.');
      return;
    }
    var header = ['month', 'hours_saved_actual', 'matters_handled', 'note', 'created_at'];
    var lines = [header.join(',')];
    var sorted = rows.slice().sort(function (a, b) { return a.month.localeCompare(b.month); });
    sorted.forEach(function (r) {
      var esc = function (s) {
        s = (s == null ? '' : String(s));
        return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
      };
      lines.push([esc(r.month), esc(r.hours_saved_actual), esc(r.matters_handled), esc(r.note || ''), esc(r.created_at)].join(','));
    });
    var blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'lexflow-roi-progress.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    try { URL.revokeObjectURL(a.href); } catch (e) {}
  }

  var saveBtn = $('tp_save');
  if (saveBtn) saveBtn.addEventListener('click', save);
  var exportBtn = $('tp_export');
  if (exportBtn) exportBtn.addEventListener('click', exportCsv);

  // set default month to the current month so the form is ready to use
  var dm = $('tp_month');
  if (dm) {
    try {
      var now = new Date();
      dm.value = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    } catch (e) {}
  }

  load();
})();
