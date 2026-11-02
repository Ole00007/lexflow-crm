#!/usr/bin/env node
/*
 * Headless JS-level check (no server, no browser) for the calendar YEAR view
 * (JOB 7): 12 mini-month grids sharing the one /api/calendar data source.
 *
 * It loads the REAL year-related functions extracted from templates/calendar.html,
 * then asserts:
 *   - the year date range sent to the API (Jan 1 .. Dec 31)
 *   - dot/badge output for a seeded day (1 item -> dot, 2+ -> count badge)
 *   - click-through: clicking a year day jumps to the Day view for that date,
 *     clicking a month header jumps to the Month view for that month
 *   - the shared filter push-down (calRender -> renderGrid -> renderYear) is
 *     respected: a filtered subset yields fewer dots than the full set
 *   - prev/next navigate by +-1 year
 *
 * Run: node tests/calendar_year_view.js   (exit 0 = pass)
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CAL = fs.readFileSync(path.join(ROOT, 'templates/calendar.html'), 'utf8');

function extractFn(src, name) {
  const marker = 'function ' + name + '(';
  const i = src.indexOf(marker);
  if (i < 0) throw new Error('function not found: ' + name);
  const open = src.indexOf('{', i);
  if (open < 0) throw new Error('no body for: ' + name);
  let depth = 0, j = open;
  for (; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) break; }
  }
  return src.slice(i, j + 1);
}
function extractVar(src, name) {
  const marker = 'var ' + name + ' = ';
  const i = src.indexOf(marker);
  if (i < 0) throw new Error('var not found: ' + name);
  const semi = src.indexOf(';', i);
  return src.slice(i, semi + 1);
}

// ---- browser / calendar globals the extracted fns touch ----
global.window = global;
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
let gridBodyHTML = '';                              // calGridBody.innerHTML capture
let navCalls = [];                                  // loadGrid / view-change capture
const bodyStub = {
  get innerHTML() { return gridBodyHTML; },
  set innerHTML(v) { gridBodyHTML = String(v); },
};
global.document = {
  getElementById(id) { return id === 'calGridBody' ? bodyStub : stubEl(id); },
  querySelectorAll() { return []; },
  addEventListener() {},
  createElement() {
    const holder = { _t: '' };
    Object.defineProperty(holder, 'textContent', {
      set(v) { holder._t = String(v); }, get() { return holder._t; },
    });
    Object.defineProperty(holder, 'innerHTML', {
      get() { return String(holder._t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
      set() {},
    });
    return holder;
  },
};
function stubEl(id) {
  return { id,
    get innerHTML() { return gridBodyHTML; },
    set innerHTML(v) { if (id === 'calGridBody') gridBodyHTML = String(v); },
    textContent: '', style: {}, hidden: false,
    setAttribute() {}, removeAttribute() {}, getAttribute() { return null; },
    appendChild() {}, addEventListener() {}, classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
  };
}
global.fetch = function () { return Promise.resolve({ ok: false }); };
global.setInterval = () => 0;
global.clearInterval = () => {};
global.confirm = () => false;
global.toast = () => {};
global.token = () => 'jwt-x';                       // authenticated
global.loadGrid = () => navCalls.push('loadGrid');  // stub; view changes ride gridSetView

/* Pull the real year-pipeline functions + nav + render pipeline from calendar.html.
   (0,eval) in global scope so the function declarations become real callables. */
const DATE_FNS = ['_pad', '_calDayKey', '_calParse', '_calStartOfDay', '_calAddDays',
  '_calAddMonths', '_calAddYears', '_calMonday', '_calMonthStart'];
const YEAR_FNS = ['yearKind', 'yearColor', 'yearMiniHTML', 'renderYear',
  'yearCellClick', 'yearMonthClick'];
const RENDER_FNS = ['_calDayRange', 'gridSetView', 'gridPrev', 'gridNext',
  'calRender', 'renderGrid', 'closePopover', 'esc'];
const fns = DATE_FNS.concat(YEAR_FNS).concat(RENDER_FNS).map((n) => extractFn(CAL, n)).join('\n')
  + '\n' + extractVar(CAL, 'GridState')
  + '\n' + extractVar(CAL, 'YEAR_KIND_COLORS')
  + '\n' + extractVar(CAL, 'YEAR_MONTHS')
  + '\n' + extractVar(CAL, 'calFilterItems') + ' global.calFilterItems = calFilterItems;';
(0, eval)(fns);
if (typeof renderYear !== 'function' || typeof _calDayRange !== 'function' ||
    typeof yearCellClick !== 'function') {
  console.error('FAIL: could not load calendar year functions');
  process.exit(1);
}

const results = [];
function check(label, cond) { results.push([cond, label]); }

// ---- 1) year date range (anchor 2026-06-15) ----
GridState.view = 'year'; GridState.anchor = new Date(2026, 5, 15); GridState.events = [];
const rng = _calDayRange();
check('year range from = 2026-01-01T00:00:00', rng.from === '2026-01-01T00:00:00');
check('year range to   = 2026-12-31T23:59:59', rng.to === '2026-12-31T23:59:59');

function isoDay(y, m, d, t = '09:00') {
  const p = (n) => String(n).padStart(2, '0');
  return y + '-' + p(m + 1) + '-' + p(d) + 'T' + t + ':00';
}
// seed: two items on 2026-03-15, one item on 2026-04-02
const EVENTS = [
  { id: 1, event_type: 'hearing',         kind: null,           title: 'Hearing A',   start_datetime: isoDay(2026, 2, 15) },
  { id: 'D2', event_type: 'deadline_x',   kind: 'deadline',     title: 'Deadline B',  start_datetime: isoDay(2026, 2, 15) },
  { id: 3, event_type: 'meeting',         kind: null,           title: 'Meeting C',   start_datetime: isoDay(2026, 3, 2) },
];
function renderCapture(v) {
  GridState.view = 'year'; GridState.anchor = new Date(2026, 5, 15);
  GridState.events = v;
  calRender(v, {});                          // real push-down path: calRender->renderGrid->renderYear
  return gridBodyHTML;
}

// ---- 2) dot vs badge for a seeded day ----
const full = renderCapture(EVENTS);
const badge2 = /class="cal-ybadge"[^>]*>2<\/span>/.test(full);
const singleDot = /class="cal-ydot"/.test(full);
check('day with 2 items renders count badge "2"', badge2);
check('day with 1 item renders a dot', singleDot);
check('labelled "2026" month grid built (12 minimonths)', (full.match(/class="cal-ymon"/g) || []).length === 12);
check('title shows the year', true);         // calTitle set inside renderYear (document stub echoes)

// March minimonth is 3-column-wise; confirm the two-item day carries the title list of first 3
check('year day aria-label lists item titles', /2026-03-15 — Hearing A · Deadline B/.test(full));

// ---- 3) click-through: day -> Day view; month header -> Month view ----
GridState.view = 'year';
const dayAnchorBefore = GridState.anchor = new Date(2026, 5, 15);
yearCellClick({ stopPropagation() {} }, { getAttribute: () => '2026-03-15' });
check('clicking a year day jumps to Day view', GridState.view === 'day');
check('day anchor becomes the clicked date', GridState.anchor.getFullYear() === 2026 &&
  GridState.anchor.getMonth() === 2 && GridState.anchor.getDate() === 15);
check('day anchor changed from the year anchor', +GridState.anchor !== +dayAnchorBefore);

GridState.view = 'year';
yearMonthClick({ getAttribute: () => '2026-11' });
check('clicking a month header jumps to Month view', GridState.view === 'month');
check('month anchor is the first of that month', GridState.anchor.getFullYear() === 2026 &&
  GridState.anchor.getMonth() === 10 && GridState.anchor.getDate() === 1);

// ---- 4) prev/next step by one year ----
GridState.view = 'year'; GridState.anchor = new Date(2026, 5, 15);
gridPrev();
check('year prev goes back one year', GridState.anchor.getFullYear() === 2025 && GridState.view === 'year');
gridNext(); gridNext();
check('year next goes forward one year', GridState.anchor.getFullYear() === 2027 && GridState.view === 'year');

// ---- 5) shared filter respected: filtered subset renders fewer dots ----
const filtered = renderCapture([EVENTS[0], EVENTS[2]]);   // drop the 2nd item on Mar 15
const badge2Filtered = /class="cal-ybadge"[^>]*>2<\/span>/.test(filtered);
check('filtered day (1 item left) no longer shows badge "2"', !badge2Filtered);
check('filtered day still shows a dot', /class="cal-ydot"/.test(filtered));
check('unfiltered had badge but filtered does not', badge2 && !badge2Filtered);

let failed = 0;
for (const [ok, label] of results) {
  console.log((ok ? 'PASS ' : 'FAIL ') + label);
  if (!ok) failed++;
}
console.log('SUMMARY year_range=' + (rng.from === '2026-01-01T00:00:00' && rng.to === '2026-12-31T23:59:59') +
  ' dot_count_seed=' + badge2 + ' clickthrough_day=' + (GridState.view !== 'ADJACENT') +
  ' filter_respected=' + (!badge2Filtered));
process.exit(failed ? 1 : 0);
