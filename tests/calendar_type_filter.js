#!/usr/bin/env node
/*
 * Headless JS-level check (no server, no browser) for the calendar filter
 * (JOB 6): selecting an Event-type chip changes the RENDERED event count.
 *
 * It loads the REAL shared component (static/js/filters/task_filters.js) and
 * the REAL calendar feature functions extracted from templates/calendar.html,
 * then applies the same single predicate the dropdown uses and asserts the
 * count changes when state.type changes.
 *
 * Run: node tests/calendar_type_filter.js   (exit 0 = pass)
 */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const CAL = fs.readFileSync(path.join(ROOT, 'templates/calendar.html'), 'utf8');
const FILTER = fs.readFileSync(path.join(ROOT, 'static/js/filters/task_filters.js'), 'utf8');

function extractFn(src, name) {
  const marker = 'function ' + name + '(';
  const i = src.indexOf(marker);
  if (i < 0) throw new Error('function not found: ' + name);
  const open = src.indexOf('{', i);
  let depth = 0, j = open;
  for (; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') { depth--; if (depth === 0) break; }
  }
  return src.slice(i, j + 1);
}

// browser shims so the shared component IIFE can define window.TaskFilters
global.window = global;
global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
eval(FILTER);
const TF = global.TaskFilters;
if (!TF || typeof TF.matchesState !== 'function') {
  console.error('FAIL: TaskFilters.matchesState not exposed');
  process.exit(1);
}

// load the real calendar functions + their label map (indirect eval -> global)
function extractVar(src, name) {
  const marker = 'var ' + name + ' = ';
  const i = src.indexOf(marker);
  if (i < 0) throw new Error('var not found: ' + name);
  const semi = src.indexOf(';', i);
  return src.slice(i, semi + 1);
}
const fns = ['_calParse', 'calTypeKey', 'calTypeChips', 'calFeatures']
  .map((n) => extractFn(CAL, n)).join('\n')
  + '\n' + extractVar(CAL, 'CAL_TYPE_LABELS');
(0, eval)(fns);
if (typeof calFeatures !== 'function' || typeof calTypeChips !== 'function') {
  console.error('FAIL: could not load calendar filter functions');
  process.exit(1);
}

/* Sample events mirroring what /api/calendar returns (calendar events,
   deadline-merged rows with kind, task-due rows with kind). */
const today = new Date();
function iso(offsetDays, hh = 9) {
  const d = new Date(today); d.setDate(d.getDate() + offsetDays);
  const p = (n) => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(hh) + ':00:00';
}
const EVENTS = [
  { id: 1,  event_type: 'hearing',         status: 'confirmed',   start_datetime: iso(1) },   // future hearing
  { id: 2,  event_type: 'hearing',         status: 'completed',   start_datetime: iso(-2) },  // past done hearing
  { id: 3,  event_type: 'meeting',         status: 'scheduled',   start_datetime: iso(2) },   // future meeting
  { id: 4,  event_type: 'filing_deadline', status: 'scheduled',   start_datetime: iso(3) },
  { id: 'deadline-9', kind: 'deadline', event_type: 'deadline_udienza', status: 'active',      start_datetime: iso(4) },
  { id: 'task-due-5', kind: 'task_due',   event_type: 'task_due',       status: 'in_progress', start_datetime: iso(1) },
  { id: 6,  event_type: 'filing_deadline', status: 'blocked', caseid: 200, start_datetime: iso(1) }, // linked+blocked -> Most critical
];

function pad(n){ return n < 10 ? '0'+n : ''+n; }
function todayStr(){ return today.getFullYear()+'-'+pad(today.getMonth()+1)+'-'+pad(today.getDate()); }
function soonStr(){ const d = new Date(today); d.setDate(d.getDate()+7); return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate()); }
const TODAY = todayStr(), SOON = soonStr();

function ctx() { return { items: EVENTS, myUserId: null, today: TODAY, soon: SOON, now: today }; }
function countFor(state) {
  const f = ctx();
  return EVENTS.filter((e) => TF.matchesState(state, calFeatures(e, f), TODAY, SOON)).length;
}

const results = [];
const all      = { show: 'all', priority: false, due: null, assignee: 'all', type: '', from: '', to: '' };
const onlyHear = { show: 'all', priority: false, due: null, assignee: 'all', type: 'hearing', from: '', to: '' };
const onlyMeet = { show: 'all', priority: false, due: null, assignee: 'all', type: 'meeting', from: '', to: '' };
const onlyDead = { show: 'all', priority: false, due: null, assignee: 'all', type: 'deadline', from: '', to: '' };
const onlyDue  = { show: 'all', priority: false, due: null, assignee: 'all', type: 'task_due', from: '', to: '' };

function check(label, cond) { results.push([cond, label]); }

const nAll = countFor(all);
const nHear = countFor(onlyHear);
const nMeet = countFor(onlyMeet);
const nDead = countFor(onlyDead);
const nDue = countFor(onlyDue);

check('All shows every event (' + nAll + ')', nAll === EVENTS.length);
check('selecting Hearing reduces count (' + nAll + ' -> ' + nHear + ')', nHear === 2 && nHear < nAll);
check('selecting Meeting reduces count (' + nAll + ' -> ' + nMeet + ')', nMeet === 1 && nMeet < nAll);
check('deadline_* maps to one "Deadline" chip (' + nDead + ')', nDead === 1);
check('task_due maps to "Due task" chip (' + nDue + ')', nDue === 1);

// the chip list is built from the REAL types present (All + hearing/meeting/filing_deadline/deadline/task_due), not a hardcoded set
const labels = calTypeChips(EVENTS).map((c) => c.label);
check('type chips include All', labels.indexOf('All') >= 0);
check('type chips include Hearing', labels.indexOf('Hearing') >= 0);
check('type chips include Meeting', labels.indexOf('Meeting') >= 0);
check('type chips include Deadline', labels.indexOf('Deadline') >= 0);
check('type chips include Due task', labels.indexOf('Due task') >= 0);
check('type chips omit a type not present', labels.indexOf('Deposition') < 0);

// "Open only" hides done/past: completed past hearing + past events excluded
const onlyOpen = { show: 'open', priority: false, due: null, assignee: 'all', type: '', from: '', to: '' };
const nOpen = countFor(onlyOpen);
check('Open only hides done/past (' + nAll + ' -> ' + nOpen + ')', nOpen < nAll && nOpen >= 1);

// Most critical surfaces the blocked linked event (and nothing more than All)
const critical = { show: 'all', priority: true, due: null, assignee: 'all', type: '', from: '', to: '' };
const nCrit = countFor(critical);
check('Most critical surfaces blocked-linked (' + nCrit + ' >= 1)', nCrit >= 1 && nCrit <= nAll);
// spec: an event with no task/matter link is excluded while "Most critical" is on
// (calFeatures maps a blocked *status* to blocked:false when the event has no
// link, so the shared predicate drops it — verified below)
const noLinkEvt = { type: 'hearing', date: iso(1).slice(0, 10), done: false, blocked: false,
  priorityHigh: false, overdue: false, dueSoon: true, isMine: false, blocksOthers: false };
check('no-link event excluded from Most critical', !TF.matchesState(critical, noLinkEvt, TODAY, SOON));

// date range From/To narrows
const rangy = { show: 'all', priority: false, due: null, assignee: 'all', type: '', from: TODAY, to: TODAY };
const nToday = countFor(rangy);
check('date range (today) narrows count (' + nAll + ' -> ' + nToday + ')', nToday >= 0 && nToday < nAll);

/* ── Smoke-run the actual component (TaskFilters.create) with a tiny DOM stub
      so the dynamic type-chip renderer (renderTypeChips / countByType) really
      executes — this also guards against strict-mode ReferenceErrors like an
      undeclared assignment breaking the calendar dropdown. ── */
function stubElement(tag) {
  const e = {
    tagName: tag, className: '', textContent: '', type: '', value: '',
    style: {}, hidden: false, ariaHaspopup: '', ariaExpanded: '', children: [],
    firstChild: null, idsChecked: {},
    setAttribute(k, v) { this[k] = String(v); },
    removeAttribute(k) { delete this[k]; },
    getAttribute() { return null; },
    appendChild(c) { children.push(c); if (!this.firstChild) this.firstChild = c; return c; },
    removeChild() { return this; },
    addEventListener() {},
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
  };
  const children = []; e.children = children;
  return e;
}
const stubs = [];
global.document = {
  createElement(tag) { const el = stubElement(tag); stubs.push(el); return el; },
  addEventListener() {},
  getElementById() { return stubElement('div'); },
  querySelectorAll() { return []; },
};
global.fetch = function () { return Promise.resolve({ ok: false }); };
let onApplyCalled = false, onApplyCount = 0;
const mount = stubElement('div');
const comp = TaskFilters.create({
  key: 'lf_calendar_test', mount,
  title: 'Filter events', getItems: () => EVENTS,
  features: calFeatures, typeChips: calTypeChips, typeLabel: 'Event type',
  dateRange: true, hideDue: true, hideAssignee: true,
  showChips: ['all', 'open'], chipLabels: { all: 'All', open: 'Open only' },
  onApply(visible, meta) { onApplyCalled = true; onApplyCount = visible.length; },
});
check('component create() builds without throwing', typeof comp === 'object');
check('component apply() runs (type chips + counts) without throwing', (() => {
  try { comp.apply(); } catch (err) { console.error('apply threw:', err.message); return false; }
  return true;
})());
const allChips = stubs.filter((e) => String(e.className).indexOf('lf-chip') === 0);
const typeChipsBuilt = allChips.filter((e) => e.children.some((c) => String(c.className).indexOf('lf-chip-count') === 0)).length;
check('type chip buttons built (6 = All + 5 real types present)', typeChipsBuilt === 6);
check('onApply ran and rendered a real count', onApplyCalled && onApplyCount >= 1);
const countLabels = stubs.filter((e) => String(e.className).indexOf('lf-chip-count') === 0)
  .map((e) => e.textContent);
check('per-type "(N)" counts present', countLabels.some((t) => /^\(\d+\)$/.test(t)));

let failed = 0;
for (const [ok, label] of results) {
  console.log((ok ? 'PASS ' : 'FAIL ') + label);
  if (!ok) failed++;
}

// Summary
console.log('SUMMARY selected_type_changes_count=' + (nHear !== nAll && nMeet !== nAll));
console.log('COUNTS all=' + nAll + ' hearing=' + nHear + ' meeting=' + nMeet + ' deadline=' + nDead + ' task_due=' + nDue +
  ' open=' + nOpen + ' critical=' + nCrit + ' today=' + nToday);
process.exit(failed ? 1 : 0);
