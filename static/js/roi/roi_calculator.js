/* ============================================================================
 * LexFlow — ROI "time-saver & efficiency" calculator.  (PART B)
 * static/js/roi/roi_calculator.js
 *
 * PURE client-side math, bundled as a tiny testable module. No storage, no
 * tracking, no network. The only assumption treated as editable (and clearly
 * flagged) by the visitor is `hoursPerMatter` — everything else is standard
 * billable-hours arithmetic.
 *
 * Exports (window.ROICalculator):
 *   computeRoi(inputs) -> result object (see below)
 *   fmtEur(n) / fmtInt(n)  -> whole-number formatting (no fake precision)
 *   labels                -> IT/EN strings for the summary sentence
 *   init(container, lang, defaultLawyers) -> wire the page
 *
 * Model (plain words):
 *   hourly value   = annual cost per lawyer / billable hours per year
 *   hours regained = matters per month, per lawyer, × hours saved per matter
 *                    × number of lawyers × adoption ramp
 *   value of hours = hours regained × hourly value
 *   LexFlow cost   = price per lawyer per month × lawyers × months
 *   ROI (3y)       = (3y benefit − 3y LexFlow cost) / 3y LexFlow cost × 100
 *   payback        = month when cumulative net benefit turns positive
 * ========================================================================== */
(function () {
  'use strict';

  var DEFAULTS = {
    lawyers: 1,                 // number of lawyers
    annualCost: 70000,          // fully-loaded EUR / lawyer / year
    mattersPerMonth: 20,        // matters per month, per lawyer
    price: 49,                  // LexFlow EUR / lawyer / month
    hoursPerMatter: 1.5,        // ASSUMPTION — validate with a lawyer
    billableHours: 1500,        // billable hours / lawyer / year
    averageHourRate: 0,         // EUR/hour (optional override; 0/empty => fallback)
    ramp: 1.0                   // adoption ramp 0..1 (100%)
  };

  function clampNum(v, fallback, min, max) {
    var n = Number(v);
    if (!isFinite(n)) n = fallback;
    if (min != null && n < min) n = min;
    if (max != null && n > max) n = max;
    return n;
  }

  function round(n) { return Math.round(n); }

  /* Pure computation. `inputs` may be partial; missing keys fall back to
     DEFAULTS. All monetary/hour outputs are whole numbers (no fake precision). */
  function computeRoi(inputs) {
    inputs = inputs || {};
    var laws = clampNum(inputs.lawyers, DEFAULTS.lawyers, 1, 500);
    var annualCost = clampNum(inputs.annualCost, DEFAULTS.annualCost, 0, 10000000);
    var mpm = clampNum(inputs.mattersPerMonth, DEFAULTS.mattersPerMonth, 0, 100000);
    var price = clampNum(inputs.price, DEFAULTS.price, 0, 100000);
    var hpm = clampNum(inputs.hoursPerMatter, DEFAULTS.hoursPerMatter, 0, 100);
    var bh = clampNum(inputs.billableHours, DEFAULTS.billableHours, 1, 5000);
    var ramp = clampNum(inputs.ramp, DEFAULTS.ramp, 0, 1);
    var ahr = clampNum(inputs.averageHourRate, DEFAULTS.averageHourRate, 0, 100000);

    // The lawyer's average billing rate (EUR/hour). If the user filled it in, it
    // IS the hour value used for the euro value of regained hours; otherwise we
    // fall back to annual cost / billable hours (the historical behaviour).
    var hourlyRateSource = 'computed';
    var hourlyValue = bh > 0 ? annualCost / bh : 0;
    if (ahr > 0) {
      hourlyValue = ahr;
      hourlyRateSource = 'input';
    }

    var hoursPerMonthPerLawyer = mpm * hpm;
    var hoursRegainedPerMonth = hoursPerMonthPerLawyer * laws * ramp;
    var hoursRegainedPerYear = hoursRegainedPerMonth * 12;

    var valuePerMonth = hoursRegainedPerMonth * hourlyValue;
    var valuePerYear = valuePerMonth * 12;
    var value3y = valuePerYear * 3;

    var costPerMonth = price * laws;
    var costPerYear = costPerMonth * 12;
    var cost3y = costPerYear * 3;

    var net3y = value3y - cost3y;
    var roiPct = cost3y > 0 ? (net3y / cost3y) * 100 : 0;

    var monthlyNet = valuePerMonth - costPerMonth;
    var paybackMonths = null;
    if (costPerMonth > 0 && monthlyNet > 0) {
      // months until cumulative net covers the running cost (rounded to whole)
      paybackMonths = Math.ceil(costPerMonth / monthlyNet);
    } else if (costPerMonth <= 0) {
      paybackMonths = 0;
    }

    return {
      lawyers: round(laws),
      annualCost: round(annualCost),
      mattersPerMonth: round(mpm),
      price: round(price),
      hoursPerMatter: round(hpm),
      billableHours: round(bh),
      ramp: round(ramp * 100),               // percent

      hourlyValue: round(hourlyValue),
      hourlyRateSource: hourlyRateSource,     // 'input' | 'computed'
      hoursPerMonthPerLawyer: round(hoursPerMonthPerLawyer),
      hoursRegainedPerMonth: round(hoursRegainedPerMonth),
      hoursRegainedPerYear: round(hoursRegainedPerYear),
      valuePerMonth: round(valuePerMonth),
      valuePerYear: round(valuePerYear),
      value3y: round(value3y),
      costPerMonth: round(costPerMonth),
      costPerYear: round(costPerYear),
      cost3y: round(cost3y),
      net3y: round(net3y),
      roiPct: Math.round(roiPct),            // whole percent
      paybackMonths: paybackMonths,

      /* 3-year series for the bar/line chart (benefit and cost per year) */
      series: [
        { year: 1, benefit: round(valuePerYear), cost: round(costPerYear) },
        { year: 2, benefit: round(valuePerYear), cost: round(costPerYear) },
        { year: 3, benefit: round(valuePerYear), cost: round(costPerYear) }
      ]
    };
  }

  function fmtEur(n) { return '€' + Math.round(n).toLocaleString('en-US'); }
  function fmtInt(n) { return Math.round(n).toLocaleString('en-US'); }
  function fmtRamp(p) { return Math.round(p) + '%'; }

  window.ROICalculator = {
    computeRoi: computeRoi,
    DEFAULTS: DEFAULTS,
    fmtEur: fmtEur,
    fmtInt: fmtInt,
    round: round
  };
})();
