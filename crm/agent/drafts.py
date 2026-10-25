"""Deterministic draft templates (IT/EN) built from matter facts. Always labelled as a draft for lawyer review."""
from __future__ import annotations

from typing import Any, Dict, List

KINDS = ('client_update', 'document_request', 'deadline_reminder')

_T = {
    'it': {
        'banner': 'BOZZA — da rivedere e firmare dall\'avvocato prima dell\'invio',
        'hello': 'Gentile {client},',
        'bye': 'Cordiali saluti,\n[Nome e firma dello Studio]',
        'update_subject': 'Aggiornamento sulla pratica {title} ({ref})',
        'update_intro': 'Le scriviamo per aggiornarLa sullo stato della pratica "{title}" ({ref}), attualmente in stato "{status}".',
        'tasks': 'Attività in corso:',
        'deadlines': 'Prossime scadenze:',
        'none': '(nessuna al momento)',
        'req_subject': 'Richiesta di documenti — pratica {title} ({ref})',
        'req_intro': 'Per proseguire con la pratica "{title}" ({ref}) Le chiediamo di farci pervenire i seguenti documenti:',
        'req_close': 'Può inviarli rispondendo a questa email o consegnarli in studio. Grazie per la collaborazione.',
        'rem_subject': 'Promemoria scadenze — pratica {title} ({ref})',
        'rem_intro': 'Le ricordiamo le prossime scadenze relative alla pratica "{title}" ({ref}):',
        'placeholder': '[inserire i documenti richiesti]',
    },
    'en': {
        'banner': 'DRAFT — for lawyer review and signature before sending',
        'hello': 'Dear {client},',
        'bye': 'Kind regards,\n[Firm name and signature]',
        'update_subject': 'Update on your matter {title} ({ref})',
        'update_intro': 'We are writing to update you on the matter "{title}" ({ref}), currently "{status}".',
        'tasks': 'Work in progress:',
        'deadlines': 'Upcoming deadlines:',
        'none': '(none at the moment)',
        'req_subject': 'Document request — matter {title} ({ref})',
        'req_intro': 'To move forward with the matter "{title}" ({ref}) we kindly ask you to send us the following documents:',
        'req_close': 'You may reply to this email or bring them to the office. Thank you for your cooperation.',
        'rem_subject': 'Deadline reminder — matter {title} ({ref})',
        'rem_intro': 'This is a reminder of the upcoming deadlines for the matter "{title}" ({ref}):',
        'placeholder': '[list the requested documents]',
    },
}


def _bullets(rows: List[str], none: str) -> str:
    return '\n'.join(f'- {r}' for r in rows) if rows else none


def build_draft(kind: str, lang: str, matter: Dict[str, Any], tasks: List[Dict[str, Any]],
                events: List[Dict[str, Any]], note: str = '') -> Dict[str, str]:
    t = _T.get(lang, _T['en'])
    title = matter.get('title') or '—'
    ref = matter.get('display_id') or matter.get('case_no') or f"#{matter.get('id')}"
    client = (matter.get('contact_name') or '').replace('(client)', '').strip() or ('Cliente' if lang == 'it' else 'Client')
    ctx = {'title': title, 'ref': ref, 'status': matter.get('status') or '—', 'client': client}
    open_tasks = [f"{x.get('title')}" + (f" (entro {x['duedate']})" if lang == 'it' and x.get('duedate') else
                                         f" (due {x['duedate']})" if x.get('duedate') else '')
                  for x in tasks if str(x.get('status', '')).lower() not in ('done', 'closed')][:6]
    ev_rows = [f"{str(e.get('start_datetime', ''))[:16].replace('T', ' ')} — {e.get('title')}" for e in events][:6]
    if kind == 'document_request':
        subject = t['req_subject'].format(**ctx)
        body = [t['req_intro'].format(**ctx), note.strip() and f'- {note.strip()}' or f"- {t['placeholder']}", '', t['req_close']]
    elif kind == 'deadline_reminder':
        subject = t['rem_subject'].format(**ctx)
        body = [t['rem_intro'].format(**ctx), _bullets(ev_rows or [f"{x.get('title')}" for x in tasks if x.get('duedate')][:6], t['none'])]
    else:
        subject = t['update_subject'].format(**ctx)
        # Internal task titles are NOT put in a client letter (they may be internal workflow labels).
        n = len(open_tasks)
        progress = (f"Al momento ci sono {n} attività in corso sulla pratica." if lang == 'it'
                    else f"There are currently {n} activities in progress on the matter.")
        body = [t['update_intro'].format(**ctx), '', progress, '', t['deadlines'], _bullets(ev_rows, t['none'])]
        if note.strip():
            body += ['', note.strip()]
    text = '\n'.join([t['banner'], '', subject, '', t['hello'].format(**ctx), ''] + body + ['', t['bye']])
    return {'subject': subject, 'text': text}
