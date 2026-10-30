// Pure JS model tests for the LexFlow ROI calculator (JOB 5).
// Run with: node tests/roi_js_model_test.js   (also invoked from pytest)
// Covers: conservative & expected scenarios, derive-from-baseline path,
//         setup cost / payback, ramp-up months, assistants, no-bare-ROI.
'use strict';
var path = require('path');
global.window = {}; // module expects a browser global; expose one for Node
require(path.join(__dirname, '..', 'static', 'js', 'roi', 'roi_calculator.js'));
var RC = global.window.ROICalculator;

var failures = 0;
function ok(cond, msg) {
  if (cond) { console.log('  ✓ ' + msg); }
  else { failures++; console.error('  ✗ FAIL: ' + msg); }
}
function approx(a, b, tol, msg) { ok(Math.abs(a - b) <= (tol == null ? 0.5 : tol), msg + ' (got ' + a + ', want ~' + b + ')'); }

console.log('defaults conserved (JOB 5): hoursPerMatter=0.5, two scenarios');
ok(RC.DEFAULTS.hoursPerMatter === 0.5, 'hoursPerMatter default is the CONSERVATIVE 0.5h base, not 1.5');
var keys = Object.keys(RC.SCENARIOS || {});
ok(keys.indexOf('conservative') !== -1 && keys.indexOf('expected') !== -1, 'both scenario keys exist (' + keys.join(',') + ')');
ok(RC.SCENARIOS.conservative.hoursMultiplier === 1.0 && RC.SCENARIOS.conservative.adoption === 0.70 && RC.SCENARIOS.conservative.realisation === 0.50, 'conservative = x1.0 / 70% / 50%');
ok(RC.SCENARIOS.expected.hoursMultiplier === 1.6 && RC.SCENARIOS.expected.adoption === 0.90 && RC.SCENARIOS.expected.realisation === 0.70, 'expected = x1.6 / 90% / 70%');

console.log('— 1 lawyer default —');
var r1 = RC.computeScenarios({ lawyers: 1 });
ok(r1.method === 'flat', 'flat method when baseline empty');
approx(r1.conservative.roiPct, 224, 1, 'conservative ROI% no longer +2757 (got ~224)');
ok(r1.conservative.roiPct < 2757, 'conservative ROI% well below the old +2757 headline');
approx(r1.conservative.value3y, 5717, 1, 'conservative 3y value €~5717');
approx(r1.conservative.cost3y, 1764, 1, 'conservative 3y cost €1764');
approx(r1.conservative.net3y, 3953, 1, 'conservative net €~3953');
approx(r1.expected.roiPct, 833, 1, 'expected ROI% ~833');
approx(r1.expected.value3y, 16464, 1, 'expected 3y value €~16464');
approx(r1.expected.hoursRegainedPerMonth, 14, 1, 'expected regained hrs/mo ~14');
approx(r1.conservative.hoursRegainedPerMonth, 7, 1, 'conservative regained hrs/mo ~7');

console.log('— 10 lawyers default (ROI invariant, € scales) —');
var r10 = RC.computeScenarios({ lawyers: 10 });
approx(r10.conservative.value3y, 57167, 200, 'conservative 10-lawyer 3y value ~€57167');
approx(r10.conservative.cost3y, 17640, 1, '10-lawyer cost €17640');
ok(Math.abs(r10.conservative.roiPct - r1.conservative.roiPct) < 0.5, 'ROI% invariant to scale (1 vs 10 lawyers)');
approx(r10.expected.value3y, 164640, 1000, 'expected 10-lawyer ~€164640');

console.log('— derive-from-baseline path —');
var d = RC.computeScenarios({ baselineHoursPerMatter: 4, baselineReductionPct: 40 });
ok(d.method === 'derived', 'method flips to derived when baseline filled');
approx(d.baseHoursPerMatter, 1.6, 0.01, 'baseHPM derived = 4 × 40% = 1.6h');
approx(d.conservative.effectiveHoursPerMatter, 1.6, 0.01, 'conservative effective HPM = derived x1.0');
approx(d.expected.effectiveHoursPerMatter, 2.56, 0.01, 'expected effective HPM = 1.6 x 1.6');
var dHigh = RC.computeScenarios({ baselineHoursPerMatter: 4, baselineReductionPct: 40, mattersPerMonth: 20 });
ok(dHigh.conservative.value3y > r1.conservative.value3y, 'derived baseline increases value vs flat assumption');

console.log('— setup cost / training / payback —');
var s = RC.computeScenarios({ lawyers: 1, setupCost: 2000, trainingHours: 4 });
ok(s.conservative.oneOffCost3y >= 2000, 'one-off cost ≥ setup');
var rawTraining = 4 * 1 * Math.round(s.conservative.hourlyValue);
ok(s.conservative.oneOffCost3y >= 2000 + rawTraining - 1, 'one-off includes training valued at hour rate (' + rawTraining + ')');
ok(s.conservative.cost3y >= s.conservative.costPerMonth * 36, 'cost3y includes one-off on top of subscription');
var sp = RC.computeScenarios({ lawyers: 1, setupCost: 3000, trainingHours: 0 });
ok(sp.conservative.paybackMonths !== null && sp.conservative.paybackMonths > 1, 'one-off setup pushes payback later than month 1 (' + sp.conservative.paybackMonths + ')');
ok(sp.expected.paybackMonths !== null && sp.expected.paybackMonths <= sp.conservative.paybackMonths, 'expected pays back no later than conservative with same setup (' + sp.conservative.paybackMonths + ' vs ' + sp.expected.paybackMonths + ')');
// a very large one-off on a small firm legitimately never pays back in 3y
var spBig = RC.computeScenarios({ lawyers: 1, setupCost: 99999 });
ok(spBig.conservative.paybackMonths === null, 'huge setup => no payback within horizon (honest null, not fake number)');
console.log('  ∞ sanity: setupCost=300 payback ' + sp.conservative.paybackMonths + 'mo, setup=99999 payback ' + spBig.conservative.paybackMonths);

console.log('— ramp-up months —');
var rampSlow = RC.computeScenarios({ rampUpMonths: 12 });
var rampFast = RC.computeScenarios({ rampUpMonths: 1 });
ok(rampSlow.conservative.value3y < rampFast.conservative.value3y, 'longer ramp-up => lower 3y benefit');
ok(rampSlow.conservative.value3y > 0, 'ramp still yields positive benefit');
// month-1 series should scale with ramp
ok(rampSlow.conservative.series[0].benefit < rampSlow.conservative.series[2].benefit, 'year-1 benefit below full (ramp) in slow scenario');

console.log('— assistants add regained hours at their own value —');
var baseA = RC.computeScenarios({ lawyers: 1 }).conservative;
var withAssist = RC.computeScenarios({ lawyers: 1, assistants: 2, assistantAnnualCost: 30000 }).conservative;
ok(withAssist.hoursRegainedPerMonth > baseA.hoursRegainedPerMonth, 'assistants add regained hours/month');
ok(withAssist.valuePerMonth !== baseA.valuePerMonth, 'assistants add euro value');

console.log('— ROI% never bare: every result carries the € pair —');
var all = RC.computeScenarios({ lawyers: 1 });
ok(typeof all.conservative.value3y === 'number' && typeof all.conservative.cost3y === 'number', 'ROI always alongside 3y benefit & 3y cost €');

console.log('— back-compat computeRoi returns conservative + .expected —');
var cr = RC.computeRoi({ lawyers: 1, averageHourRate: 100 });
ok(cr.scenarioKey === 'conservative' && cr.expected && cr.expected.scenarioKey === 'expected', 'computeRoi defaults to conservative and exposes .expected');
ok(cr.hourlyRateSource === 'input' && cr.hourlyValue === 100, 'hourly-rate override still honoured (fallback logic kept)');
var cf = RC.computeRoi({ lawyers: 1 });
ok(cf.hourlyRateSource === 'computed', 'computed source flag when rate empty');
ok(Math.abs(cf.hourlyValue - Math.round(70000 / 1500)) < 1, 'computed hour value = annualCost/billable');

console.log(failures === 0 ? '\nALL PASS' : '\n' + failures + ' FAILURES');
process.exit(failures === 0 ? 0 : 1);
