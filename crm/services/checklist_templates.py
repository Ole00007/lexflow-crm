"""Matter-stage checklist TEMPLATES (WS-K, feat/wave2-checklist).

Stage templates are DATA, not a table: a matter's checklist is instantiated by
copying one of these templates into MatterChecklistItem rows (see
crm/routes/checklist.py::init). Keeping templates as code means no extra table,
no migration when a template changes, and a single reviewable source of truth.

DRAFT — the Italian family-law template below is a STARTING POINT and must be
validated by a qualified lawyer before use with real clients. Nothing here is
legal advice; procedural steps and document names are indicative only.

Each template:
    key    -> stable identifier used by the API
    label  -> human label (shown in the template picker)
    stages -> ordered list of {key, name, items[]}
Each item:
    label        -> English label with the Italian document/term in parentheses
    kind         -> 'document' | 'action' | 'deadline'   (mirrors the model)
    required_doc -> Italian document name when kind == 'document' (else None)
    owner_role   -> default owner, one of crm.models.task_assignee.TASK_ROLES
                    (case_owner / docs_supply / legal_assistant / lawyer_review)

Stage keys are NAMESPACED per template (e.g. 'sep_documents', 'gen_intake') so a
single global STAGE_NAMES lookup can resolve a stage name from an item's
stage_key without storing the template key on the case.
"""

# Reuse the Gantt role keys — single source of truth is TASK_ROLES.
from ..models.task_assignee import TASK_ROLES  # noqa: F401  (validation reference)

# Header shown on every template / instantiated checklist.
TEMPLATE_DISCLAIMER = (
    "DRAFT — to be validated by a qualified lawyer before use with real clients"
)


def _doc(label, required_doc, owner_role='docs_supply'):
    return {'label': label, 'kind': 'document', 'required_doc': required_doc, 'owner_role': owner_role}


def _action(label, owner_role='case_owner'):
    return {'label': label, 'kind': 'action', 'required_doc': None, 'owner_role': owner_role}


def _deadline(label, owner_role='case_owner'):
    return {'label': label, 'kind': 'deadline', 'required_doc': None, 'owner_role': owner_role}


# ── family_separation_it: separazione consensuale / giudiziale (IT civil) ─────
_FAMILY_SEPARATION_IT = {
    'key': 'family_separation_it',
    'label': 'Separazione (Italian family law) — DRAFT',
    'disclaimer': TEMPLATE_DISCLAIMER,
    'stages': [
        {'key': 'sep_intake', 'name': '1 · Intake & conflict check', 'items': [
            _action('Open matter and record client details', 'case_owner'),
            _action('Conflict-of-interest check (verifica conflitto di interessi)', 'lawyer_review'),
            _action('Confirm separation type: consensuale or giudiziale', 'lawyer_review'),
        ]},
        {'key': 'sep_mandate', 'name': '2 · Mandate & engagement', 'items': [
            _doc('Power of attorney (procura alle liti)', 'Procura alle liti', 'legal_assistant'),
            _doc('Privacy notice & consent (informativa privacy / consenso)', 'Informativa privacy', 'legal_assistant'),
            _doc('Engagement letter (lettera di incarico)', 'Lettera di incarico', 'legal_assistant'),
        ]},
        {'key': 'sep_documents', 'name': '3 · Client documents', 'items': [
            _doc('Marriage certificate (certificato di matrimonio)', 'Certificato di matrimonio'),
            _doc('Family status certificate (stato di famiglia)', 'Stato di famiglia'),
            _doc('Residence certificate (certificato di residenza)', 'Certificato di residenza'),
            _doc('Tax returns, last 3 years (dichiarazioni dei redditi, ultimi 3 anni)', 'Dichiarazioni dei redditi'),
            _doc('Bank statements (estratti conto)', 'Estratti conto'),
            _doc('Agreement / proposal if consensuale (accordi / proposte)', 'Accordi / proposte'),
            _doc('Children documentation (documentazione figli)', 'Documentazione figli'),
        ]},
        {'key': 'sep_drafting', 'name': '4 · Drafting', 'items': [
            _action('Draft petition (bozza ricorso per separazione)', 'legal_assistant'),
            _action('Lawyer review of draft (revisione avvocato)', 'lawyer_review'),
        ]},
        {'key': 'sep_filing', 'name': '5 · Filing', 'items': [
            _action('Electronic filing (deposito telematico PCT)', 'case_owner'),
            _doc('Court fees paid (contributo unificato / marca da bollo)', 'Contributo unificato', 'case_owner'),
        ]},
        {'key': 'sep_service', 'name': '6 · Service / notification', 'items': [
            _action('Service / notification to counterparty (notifica)', 'case_owner'),
        ]},
        {'key': 'sep_hearing', 'name': '7 · Hearing preparation', 'items': [
            _deadline('Presidential hearing (udienza presidenziale)', 'lawyer_review'),
            _action('Prepare client for hearing (preparazione udienza)', 'lawyer_review'),
        ]},
        {'key': 'sep_post_hearing', 'name': '8 · Post-hearing', 'items': [
            _action('Record court orders (provvedimenti del giudice)', 'case_owner'),
            _action('Plan next steps (prossimi adempimenti)', 'case_owner'),
        ]},
    ],
}

# ── generic_civil: minimal generic civil matter ──────────────────────────────
_GENERIC_CIVIL = {
    'key': 'generic_civil',
    'label': 'Generic civil matter — DRAFT',
    'disclaimer': TEMPLATE_DISCLAIMER,
    'stages': [
        {'key': 'gen_intake', 'name': '1 · Intake & conflict check', 'items': [
            _action('Open matter and record client details', 'case_owner'),
            _action('Conflict-of-interest check', 'lawyer_review'),
        ]},
        {'key': 'gen_mandate', 'name': '2 · Mandate & engagement', 'items': [
            _doc('Power of attorney (procura)', 'Procura', 'legal_assistant'),
            _doc('Privacy notice & consent (informativa privacy)', 'Informativa privacy', 'legal_assistant'),
            _doc('Engagement letter (lettera di incarico)', 'Lettera di incarico', 'legal_assistant'),
        ]},
        {'key': 'gen_documents', 'name': '3 · Documents', 'items': [
            _doc('Core supporting documents (documentazione di supporto)', 'Documentazione di supporto'),
        ]},
        {'key': 'gen_drafting', 'name': '4 · Drafting & review', 'items': [
            _action('Draft principal act (bozza atto)', 'legal_assistant'),
            _action('Lawyer review (revisione avvocato)', 'lawyer_review'),
        ]},
        {'key': 'gen_filing', 'name': '5 · Filing', 'items': [
            _action('File / submit (deposito)', 'case_owner'),
        ]},
        {'key': 'gen_closing', 'name': '6 · Closing', 'items': [
            _action('Close matter and archive (chiusura e archiviazione)', 'case_owner'),
        ]},
    ],
}

TEMPLATES = {
    _FAMILY_SEPARATION_IT['key']: _FAMILY_SEPARATION_IT,
    _GENERIC_CIVIL['key']: _GENERIC_CIVIL,
}

# Global stage_key -> stage name lookup (keys are namespaced, so no collisions).
STAGE_NAMES = {}
for _t in TEMPLATES.values():
    for _s in _t['stages']:
        STAGE_NAMES[_s['key']] = _s['name']


def get_template(key):
    """Return the template dict for `key`, or None."""
    return TEMPLATES.get(key)


def list_templates():
    """Return a compact list for the API: key, label, disclaimer, stage names."""
    out = []
    for t in TEMPLATES.values():
        out.append({
            'key': t['key'],
            'label': t['label'],
            'disclaimer': t.get('disclaimer', TEMPLATE_DISCLAIMER),
            'stages': [{'key': s['key'], 'name': s['name']} for s in t['stages']],
        })
    return out


def stage_name(stage_key):
    """Resolve a stage_key to its human name (falls back to the raw key)."""
    return STAGE_NAMES.get(stage_key, stage_key)


def iter_template_items(key):
    """Yield (position, stage_key, item_dict) in template order with a GLOBAL
    monotonic position, so `position` alone orders the whole checklist and the
    (caseid, stage_key, position) unique constraint always holds."""
    t = get_template(key)
    if not t:
        return
    pos = 0
    for stage in t['stages']:
        for item in stage['items']:
            yield pos, stage['key'], item
            pos += 1
