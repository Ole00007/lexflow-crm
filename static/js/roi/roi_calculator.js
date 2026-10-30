/* ============================================================================
 * LexFlow — ROI "time-saver & efficiency" calculator.  (PART B / JOB 5)
 * static/js/roi/roi_calculator.js
 *
 * PURE client-side math, bundled as a tiny testable module. No storage, no
 * tracking, no network.
 *
 * Two scenarios, side by side — CONSERVATIVE first (the headline), EXPECTED
 * clearly labelled "if adoption goes well":
 *   conservative = hours-saved ×1.0 of the 0.5h base, 70% adoption, only 50%
 *                  of regained hours monetised (realisation).
 *   expected     = hours-saved ×1.6 (0.8h), 90% adoption, 70% monetised.
 *   Scenario multipliers (hours / adoption / realisation) are editable under
 *   "Use your own figures". ROI% is NEVER shown without the € amounts beside it.
 *
 * Hours-saved method (the page shows WHICH one produced the number):
 *   flat     — in_hmatter (base hours/matter, default 0.5). Used by default.
 *   derived  — baseline admin/drafting hours TODAY (in_baseline_hours) reduced
 *              by the % LexFlow cuts (in_baseline_reduction). When the baseline
 *              field is filled it OVERRIDES the flat value; the derived hours
 *              still get the scenario multiplier applied.
 *
 * Extra "your own figures" inputs:
 *   baselineHoursPerMatter, baselineReductionPct (-> derived method)
 *   realisation (per scenario, share of regained hours that becomes value)
 *   setupCost (one-off €), trainingHours per lawyer (one-off, valued at hour
 *              rate)
 *   assistants + assistantAnnualCost (optional; adds their regained hours at
 *              their own hour value)
 *   rampUpMonths (default 3): linear adoption ramp 0 -> full over N months.
 *
 * Exports (window.ROICalculator):
 *   computeRoi(inputs)                -> CONSERVATIVE scenario (back-compat)
 *   computeScenarios(inputs)          -> { conservative, expected, method,
 *                                         baseHoursPerMatter, inputsUsed }
 *   DEFAULTS / SCENARIOS / fmtEur / fmtInt / fmtPct / round
 * ========================================================================== */
(function () {
  'use strict';

  var DEFAULTS = {
    lawyers: 1,                 // number of lawyers
    annualCost: 70000,          // fully-loaded EUR / lawyer / year
    mattersPerMonth: 20,        // matters per month, per lawyer
    price: 49,                  // LexFlow EUR / lawyer / month
    hoursPerMatter: 0.5,        // base ASSUMPTION (flat) — validate with a lawyer
    billableHours: 1500,        // billable hours / lawyer / year
    averageHourRate: 0,         // EUR/hour (optional override; 0/empty => fallback)
    // JOB 5 — "your own figures"
    baselineHoursPerMatter: 0,  // 0 => flat method; >0 => derived overrides flat
    baselineReductionPct: 40,   // % LexFlow cuts baseline hours (derived)
    setupCost: 0,               // one-off EUR setup / onboarding
    trainingHours: 0,           // one-off training hours per lawyer
    assistants: 0,              // optional legal assistants
    assistantAnnualCost: 30000, // EUR / assistant / year
    rampUpMonths: 3             // months of linear adoption ramp-up
  };

  // Scenario multipliers (editable via inputs.scenarios.<name>).
  var SCENARIOS = {
    conservative: { hoursMultiplier: 1.0, adoption: 0.70, realisation: 0.50 },
    expected:     { hoursMultiplier: 1.6, adoption: 0.90, realisation: 0.70 }
  };
  var SCENARIO_KEYS = Object.keys(SCENARIOS); // ['conservative','expected']

  var HORIZON = 36; // 3 years (months) — keep in sync with the UI label

  function clampNum(v, fallback, min, max) {
    var n = Number(v);
    if (!isFinite(n)) n = fallback;
    if (min != null && n < min) n = min;
    if (max != null && n > max) n = max;
    return n;
  }

  function round(n) { return Math.round(n); }
  /* Round to 2 decimals for fractional display fields (hours per matter). */
  function r2(n) { return Math.round(n * 100) / 100; }

  function scenarioConfig(inputs, name) {
    var def = SCENARIOS[name];
    var user = (inputs && inputs.scenarios && inputs.scenarios[name]) || {};
    return {
      hoursMultiplier: clampNum(user.hoursMultiplier, def.hoursMultiplier, 0, 100),
      adoption: clampNum(user.adoption, def.adoption, 0, 1),
      realisation: clampNum(user.realisation, def.realisation, 0, 1)
    };
  }

  function pctToFrac(inputs, key) { return clampNum(inputs[key], DEFAULTS[key], 0, 100) / 100; }

  /* Pure computation. `inputs` may be partial; missing keys fall back to
     DEFAULTS. Returns { conservative, expected, method, baseHoursPerMatter,
     inputsUsed }. `method` is 'flat' | 'derived'. All money/hours whole. */
  function computeScenarios(inputs) {
    inputs = inputs || {};
    var annualCost = clampNum(inputs.annualCost, DEFAULTS.annualCost, 0, 10000000);
    var mpm = clampNum(inputs.mattersPerMonth, DEFAULTS.mattersPerMonth, 0, 100000);
    var price = clampNum(inputs.price, DEFAULTS.price, 0, 100000);
    var hpm = clampNum(inputs.hoursPerMatter, DEFAULTS.hoursPerMatter, 0, 100);
    var bh = clampNum(inputs.billableHours, DEFAULTS.billableHours, 1, 5000);
    var ahr = clampNum(inputs.averageHourRate, DEFAULTS.averageHourRate, 0, 100000);
    var baselineHoursPerMatter = clampNum(inputs.baselineHoursPerMatter, DEFAULTS.baselineHoursPerMatter, 0, 1000);
    var reduction = pctToFrac(inputs, 'baselineReductionPct');
    var setupCost = clampNum(inputs.setupCost, DEFAULTS.setupCost, 0, 100000000);
    var trainingHours = clampNum(inputs.trainingHours, DEFAULTS.trainingHours, 0, 10000);
    var assistants = clampNum(inputs.assistants, DEFAULTS.assistants, 0, 500);
    var assistantAnnualCost = clampNum(inputs.assistantAnnualCost, DEFAULTS.assistantAnnualCost, 0, 10000000);
    var rampUpMonths = clampNum(inputs.rampUpMonths, DEFAULTS.rampUpMonths, 0, HORIZON);
    var billableHoursPerYear = bh;

    // The lawyer's average billing rate (EUR/hour). If the user filled it in, it
    // IS the hour value used for the euro value of regained hours; otherwise we
    // fall back to annual cost / billable hours (the historical behaviour).
    var hourlyRateSource = 'computed';
    var hourlyValue = bh > 0 ? annualCost / bh : 0;
    if (ahr > 0) {
      hourlyValue = ahr;
      hourlyRateSource = 'input';
    }
    var assistantHourly = bh > 0 ? assistantAnnualCost / bh : 0;

    // hours-saved method: derived (baseline shown) overrides the flat value.
    var method = 'flat';
    var baseHoursPerMatter = hpm;
    if (baselineHoursPerMatter > 0) {
      method = 'derived';
      baseHoursPerMatter = baselineHoursPerMatter * reduction;
    }

    function computeScenario(name) {
      var cfg = scenarioConfig(inputs, name);
      var effHPM = baseHoursPerMatter * cfg.hoursMultiplier;
      var costPerMonth = price * (numFrom(inputs, 'lawyers', DEFAULTS.lawyers, 1, 500, true));
      var lawyers = clampNum(inputs.lawyers, DEFAULTS.lawyers, 1, 500);

      // full-adoption steady (per month) values, before ramp & adoption cut.
      var fullHoursValuables = mpm * effHPM * lawyers * hourlyValue; // lawyers only
      var fullHoursAssistValuables = mpm * effHPM * assistants * assistantHourly;
      var fullBenefitPerMonth = (fullHoursValuables + fullHoursAssistValuables) * cfg.realisation;

      var oneOffCost = setupCost + trainingHours * lawyers * hourlyValue;

      // 36-month series: cost includes the one-off in month 1 (so cumulative
      // NET starts at 0 — the one-off is captured via month-1 cost, not doubled).
      var benefit = [], cost = [];
      var cumNet = 0;
      var paybackMonths = null;
      for (var m = 1; m <= HORIZON; m++) {
        var ramp = rampUpMonths > 0 ? Math.min(m / rampUpMonths, 1) : 1;
        var benefitThisMonth = fullBenefitPerMonth * cfg.adoption * ramp;
        var costThisMonth = costPerMonth + (m === 1 ? oneOffCost : 0);
        benefit.push(benefitThisMonth); cost.push(costThisMonth);
        cumNet += benefitThisMonth - costThisMonth;
        if (paybackMonths == null && cumNet >= 0) paybackMonths = m;
      }

      // steady (post-ramp) headline numbers for the two cards
      var hoursSteady = mpm * effHPM * (lawyers + assistants) * cfg.adoption;
      var valueSteady = fullBenefitPerMonth * cfg.adoption;
      var benefitPerYear = [];
      for (var y = 0; y < 3; y++) {
        var by = 0, cy = 0;
        for (var i = y * 12; i < y * 12 + 12; i++) { by += benefit[i]; cy += cost[i]; }
        benefitPerYear.push({ year: y + 1, benefit: by, cost: cy });
      }
      var benefit3y = benefit.reduce(function (a, b) { return a + b; }, 0);
      var cost3y = cost.reduce(function (a, b) { return a + b; }, 0);
      var net3y = benefit3y - cost3y;
      var roiPct = cost3y > 0 ? (net3y / cost3y) * 100 : 0;

      return {
        name: name === 'conservative' ? 'conservative' : 'expected',
        scenarioKey: name === 'conservative' ? 'conservative' : 'expected',
        hoursMultiplier: cfg.hoursMultiplier,
        adoption: cfg.adoption,
        realisation: cfg.realisation,
        effectiveHoursPerMatter: r2(effHPM),
        method: method,
        hourlyValue: round(hourlyValue),
        hourlyRateSource: hourlyRateSource,

        hoursRegainedPerMonth: round(hoursSteady),
        hoursRegainedPerYear: round(hoursSteady * 12),
        valuePerMonth: round(valueSteady),
        valuePerYear: round(valueSteady * 12),

        value3y: round(benefit3y),
        costPerMonth: round(costPerMonth),
        costPerYear: round(costPerMonth * 12),
        cost3y: round(cost3y),
        oneOffCost3y: round(oneOffCost),
        net3y: round(net3y),
        roiPct: Math.round(roiPct),
        paybackMonths: paybackMonths,
        series: benefitPerYear.map(function (p) {
          return { year: p.year, benefit: round(p.benefit), cost: round(p.cost) };
        })
      };
    }

    function numFrom(inputs, key, fb, min, max, int) {
      return clampNum(inputs[key], fb, min, max);
    }

    var conservative = computeScenario('conservative');
    var expected = computeScenario('expected');

    return {
      conservative: conservative,
      expected: expected,
      method: method,
      baseHoursPerMatter: r2(baseHoursPerMatter),
      hourlyValue: round(hourlyValue),
      hourlyRateSource: hourlyRateSource,
      inputsUsed: null
    };
  }

  /* Back-compat: returns the CONSERVATIVE scenario result from PART B's old
     shape (plus JOB 5 fields + the pair via .expected / .scenarios), so the
     in-app tracker and earlier tests keep working. */
  function computeRoi(inputs) {
    var all = computeScenarios(inputs);
    var r = all.conservative;
    r.expected = all.expected;
    r.scenarios = { conservative: all.conservative, expected: all.expected };
    r.savedHoursMethod = all.method;
    r.baseHoursPerMatter = all.baseHoursPerMatter;
    r.ramp = Math.round(all.conservative.adoption * 100); // legacy adoption %
    var laws = clampNum((inputs && inputs.lawyers) || DEFAULTS.lawyers, DEFAULTS.lawyers, 1, 500);
    r.lawyers = round(laws);
    r.annualCost = round(clampNum((inputs && inputs.annualCost), DEFAULTS.annualCost, 0, 10000000));
    r.mattersPerMonth = round(clampNum((inputs && inputs.mattersPerMonth), DEFAULTS.mattersPerMonth, 0, 100000));
    r.price = round(clampNum((inputs && inputs.price), DEFAULTS.price, 0, 100000));
    r.billableHours = round(clampNum((inputs && inputs.billableHours), DEFAULTS.billableHours, 1, 5000));
    r.hoursPerMatter = r.effectiveHoursPerMatter;
    r.hoursPerMonthPerLawyer = r.hoursRegainedPerMonth;
    r.value3yAll = r.value3y; // LEGACY alias used by tests/chart
    return r;
  }

  function fmtEur(n) { return '€' + Math.round(n).toLocaleString('en-US'); }
  function fmtInt(n) { return Math.round(n).toLocaleString('en-US'); }
  function fmtPct(p) { return Math.round(p) + '%'; }

  window.ROICalculator = {
    computeRoi: computeRoi,
    computeScenarios: computeScenarios,
    DEFAULTS: DEFAULTS,
    SCENARIOS: SCENARIOS,
    SCENARIO_KEYS: SCENARIO_KEYS,
    HORIZON: HORIZON,
    fmtEur: fmtEur,
    fmtInt: fmtInt,
    fmtPct: fmtPct,
    round: round
  };
})();
