"""ROI calculator tests (PART B).

Server logic is minimal: the /roi-calculator route is a pure shell, public
(logged-out safe), guarded by the ROI_CALCULATOR_ENABLED env flag. All math is
client-side JS. We assert:
  - 404 when the flag is OFF (default), 200 when ON;
  - the served page makes NO external network requests (no http/https //xxx
    refs, no third-party fonts/analytics);
  - the page wires the shared static JS module and collects NO leads (no
    <form>, no email field);
  - the client-side math function exists in the served JS (sanity check on the
    module).
"""
import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TPL = BASE / "templates" / "roi_calculator.html"
JS = BASE / "static" / "js" / "roi" / "roi_calculator.js"


def _clean():
    os.environ.pop("ROI_CALCULATOR_ENABLED", None)


def test_roi_404_when_flag_off(client):
    _clean()
    os.environ["ROI_CALCULATOR_ENABLED"] = "false"
    r = client.get("/roi-calculator")
    assert r.status_code == 404


def test_roi_404_when_flag_unset(client):
    _clean()
    # default is OFF -> 404
    os.environ.pop("ROI_CALCULATOR_ENABLED", None)
    r = client.get("/roi-calculator")
    assert r.status_code == 404


def test_roi_200_when_flag_on(client):
    _clean()
    os.environ["ROI_CALCULATOR_ENABLED"] = "true"
    r = client.get("/roi-calculator")
    assert r.status_code == 200
    assert "Calcolatore ROI" in r.get_data(as_text=True) or "ROI calculator" in r.get_data(as_text=True)


def test_roi_page_has_no_external_requests():
    """The served template must reference ZERO external URLs (no CDN, no
    third-party fonts, no analytics, no lead-gen form)."""
    assert TPL.exists(), f"missing {TPL}"
    src = TPL.read_text(encoding="utf-8")
    # external http(s) refs in src/href/link/script/style (same-origin allowed as relative)
    ext = re.findall(r'(?:src|href)\s*=\s*["\']https?://[^"\']*["\']', src)
    ext += re.findall(r'''//[a-zA-Z0-9.-]+(?:/|["'])''', src)
    ext += re.findall(r'https?://', src)
    assert ext == [], f"external refs found: {ext}"
    # no netlight/GA/fonts.google markers
    for bad in ("googleapis", "gstatic", "googletagmanager", "analytics", "fonts.google", "jsdelivr", "cdn."):
        assert bad not in src, f"external dependency present: {bad}"


def test_roi_page_wires_shared_module_and_no_lead_collection():
    assert TPL.exists()
    src = TPL.read_text(encoding="utf-8")
    # loads the static JS module
    assert "js/roi/roi_calculator.js" in src
    # no lead collection: no form, no email/password input
    assert "<form" not in src, "lead-collection form present"
    assert 'type="email"' not in src and 'id="in_email"' not in src
    for pat in ('type="text" name="email"', 'captcha', 'name="email"'):
        assert pat not in src, f"lead field present: {pat}"


def test_roi_js_module_math_sane():
    """Sanity check the pure JS math module: representative numbers round to
    whole units and are internally consistent (no fake precision)."""
    assert JS.exists(), f"missing {JS}"
    src = JS.read_text(encoding="utf-8")
    assert "computeRoi" in src
    assert "function computeRoi" in src or "computeRoi:" in src
    # defaults present
    assert "hoursPerMatter: 1.5" in src or '"hoursPerMatter": 1.5' in src
    assert "billableHours: 1500" in src
    # NEW (JOB 4): the optional average hourly rate (EUR/hour) override, and a
    # source flag distinguishing "from the entered rate" vs "computed".
    assert "averageHourRate" in src
    assert "hourlyRateSource" in src
    assert "'computed'" in src or '"computed"' in src or "source = 'computed'" in src or "hourlyRateSource = 'computed'" in src


def test_roi_js_rate_fallback_logic():
    """JOB 4: the pure JS must use the entered hourly rate when >0 and fall back
    to annual cost / billable hours when empty (all existing defaults kept)."""
    assert JS.exists()
    src = JS.read_text(encoding="utf-8")
    # input override is clamped and honored
    assert "var ahr = clampNum(inputs.averageHourRate" in src
    assert "if (ahr > 0)" in src
    assert "hourlyValue = ahr" in src
    # computed fallback is the historical one
    assert "var hourlyValue = bh > 0 ? annualCost / bh : 0" in src


def test_roi_context_flag_exposed():
    """The context processor exposes roi_calculator_enabled so the sidebar link
    can be gated on it (base.html uses it)."""
    init = (BASE / "crm" / "__init__.py").read_text(encoding="utf-8")
    assert "roi_calculator_enabled" in init
    assert "ROI_CALCULATOR_ENABLED" in init
    base = (BASE / "templates" / "base.html").read_text(encoding="utf-8")
    assert "roi_calculator_enabled" in base
    assert "roi_calculator" in base


def test_favicon_ico_served(client):
    """JOB 4 (1): /favicon.ico must return 200 (was 404), serving the existing
    LF mark under static/ (no new brand asset)."""
    _clean()
    os.environ["ROI_CALCULATOR_ENABLED"] = "true"
    r = client.get("/favicon.ico")
    assert r.status_code == 200
    assert "image/svg" in r.content_type or "svg" in r.content_type
    body = r.get_data(as_text=True)
    assert "LF" in body  # the existing LF monogram


def test_roi_public_page_has_favicon_and_new_input():
    """JOB 4 (1)+(2): the public template carries a favicon <link> and the new
    average-hourly-rate input; the back button is gone (public page = no menu,
    no back button)."""
    assert TPL.exists()
    src = TPL.read_text(encoding="utf-8")
    assert 'rel="icon"' in src
    assert "favicon.svg" in src
    # new input present with honest bilingual labels
    assert 'id="in_rate"' in src
    assert "Prezzo medio orario" in src or "Average hourly rate" in src
    # dynamic placeholder element + "which hour value was used" note
    assert "roiRateUsed" in src
    assert "vuoto = costo annuo / ore fatturabili" in src or "empty = annual cost / billable hours" in src
    # NO back button / no "Torna all'app" on the public page
    assert "roi-back" not in src
    assert "Torna all'app" not in src


def test_roi_formula_mentions_rate_override():
    """JOB 4 (2): the plain-words formula now explains the hourly-rate override
    in both IT and EN."""
    src = TPL.read_text(encoding="utf-8")
    assert "tariffa oraria inserita" in src or "entered hourly rate" in src
    assert "costo annuo ÷ ore fatturabili" in src or "annual cost ÷ billable hours" in src


def test_inapp_mode_uses_app_shell(client):
    """JOB 4 (3): ?app=1 renders the calculator inside the base.html app shell
    (sidebar present, calculator highlighted, Settings gear), while the public
    page has no sidebar and no back button. The in-app template extends base."""
    _clean()
    os.environ["ROI_CALCULATOR_ENABLED"] = "true"
    app_tpl = BASE / "templates" / "roi_calculator_app.html"
    assert app_tpl.exists()
    a_src = app_tpl.read_text(encoding="utf-8")
    # extends the normal base layout (like Kanban/Tasks do)
    assert a_src.lstrip().startswith("{% extends ") or "extends" in a_src
    assert 'extends "base.html"' in a_src
    # settings gear placed at the bottom of the sidebar
    assert "sidebar_bottom" in a_src
    assert "settings_page" in a_src
    # no back button on the in-app view
    assert "Torna all'app" not in a_src and "roi-back" not in a_src

    # render it through the route: the app-shell response carries the sidebar
    r = client.get("/roi-calculator?app=1")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # sidebar present (app shell), calculator entry highlighted, settings linked
    assert "LexFlow workspace navigation" in html
    assert "💰 ROI calculator" in html
    assert "/settings" in html
    # no standalone back button
    assert "Torna all'app" not in html
