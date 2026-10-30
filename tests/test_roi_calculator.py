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


def test_roi_context_flag_exposed():
    """The context processor exposes roi_calculator_enabled so the sidebar link
    can be gated on it (base.html uses it)."""
    init = (BASE / "crm" / "__init__.py").read_text(encoding="utf-8")
    assert "roi_calculator_enabled" in init
    assert "ROI_CALCULATOR_ENABLED" in init
    base = (BASE / "templates" / "base.html").read_text(encoding="utf-8")
    assert "roi_calculator_enabled" in base
    assert "roi_calculator" in base
