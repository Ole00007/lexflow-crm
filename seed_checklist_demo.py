"""Demo data for the Matter-stage checklist (WS-K) — local/dev only, idempotent.

Initialises a `family_separation_it` checklist for the existing "Rasing
separazione" matter (created by seed_gantt_team_demo.py — run that FIRST) and
drives it into a believable half-done state:
  * stage 3 (client documents) is the CURRENT stage,
  * "certificato di matrimonio" is DONE,
  * "dichiarazioni dei redditi" is TODO and OVERDUE,
  * one item is BLOCKED with a reason.
Stages 1 & 2 are marked fully resolved so the stepper shows real progress.

Run (same env as seed_gantt_team_demo.py):  python seed_checklist_demo.py

No real client PII is written: labels come from the template; the matter itself
is demo data from seed_gantt_team_demo.py.
"""
from datetime import date, timedelta

from crm import create_app
from crm.extensions import db
from crm.models.case import Case
from crm.models.user import User
from crm.models.matter_checklist import MatterChecklistItem
from crm.services import checklist_templates as tpl

TEMPLATE = 'family_separation_it'
MATTER_TITLE = 'Rasing separazione'


def _init_checklist(case):
    """Idempotently instantiate the template for a case (skip if live items exist)."""
    existing = (MatterChecklistItem.query
                .filter_by(caseid=case.id, is_deleted=False).count())
    if existing:
        return existing, False
    n = 0
    for pos, stage_key, item in tpl.iter_template_items(TEMPLATE):
        db.session.add(MatterChecklistItem(
            workspace_id=case.workspace_id, caseid=case.id,
            stage_key=stage_key, position=pos,
            label=item['label'][:200], kind=item['kind'],
            required_doc=(item.get('required_doc') or None),
            owner_role=item.get('owner_role'), status='todo'))
        n += 1
    db.session.flush()
    return n, True


def _set(case, stage_key, needle, **fields):
    """Find the item in `stage_key` whose label contains `needle` and set fields."""
    it = (MatterChecklistItem.query
          .filter_by(caseid=case.id, stage_key=stage_key, is_deleted=False)
          .filter(MatterChecklistItem.label.ilike('%' + needle + '%'))
          .first())
    if not it:
        return None
    for k, v in fields.items():
        setattr(it, k, v)
    return it


def main():
    app = create_app()
    with app.app_context():
        # Ensure the checklist table exists in standalone/dev runs. In integration
        # the model is registered via crm/models/__init__.py and created by the
        # migration / create_all; this call is idempotent (creates only missing).
        db.create_all()
        case = Case.query.filter_by(title=MATTER_TITLE, is_deleted=False).first()
        admin = User.query.filter_by(email='olesya00007@yahoo.com').first()
        if not case:
            print('ERROR: matter "%s" missing — run seed_gantt_team_demo.py first' % MATTER_TITLE)
            return
        n, created = _init_checklist(case)

        # Stages 1 & 2 done (intake + mandate)
        for sk in ('sep_intake', 'sep_mandate'):
            for it in MatterChecklistItem.query.filter_by(caseid=case.id, stage_key=sk, is_deleted=False).all():
                if it.status != 'done':
                    it.status = 'done'
                    it.completed_by = admin.id if admin else None
                    it.completed_at = date.today()

        # Stage 3 (documents) = current, half done
        _set(case, 'sep_documents', 'matrimonio', status='done',
             completed_by=(admin.id if admin else None))
        _set(case, 'sep_documents', 'residence', status='done',
             completed_by=(admin.id if admin else None))
        _set(case, 'sep_documents', 'redditi', status='todo',
             due_date=date.today() - timedelta(days=4))   # OVERDUE
        _set(case, 'sep_documents', 'Bank statements', status='blocked',
             blocked_reason='Client has not provided the last-quarter estratti conto')

        db.session.commit()
        print('seeded checklist for "%s": %d items (created=%s), stage 3 current, 1 overdue, 1 blocked'
              % (MATTER_TITLE, n, created))


if __name__ == '__main__':
    main()
