# LexFlow CRM — Coordination & Orchestration

**Coordinator:** Hermes (admy_ceo profile)
**Date:** 2026-10-14
**Scope:** All LexFlow CRM workstreams — Gantt, production, security, infrastructure, tests

---

## 1. Executive summary

| Area | Status | Blocker |
|---|---|---|
| **Production** | 🔴 DOWN (day 19) | Railway access — outside repo, needs Olesia |
| **Gantt C (read-only)** | 🟡 M1 scaffold done | M1 approval + P3 authz rule |
| **Security** | 🔴 Critical gaps | A1 unprotected seed endpoint, A2 hardcoded creds |
| **Tests** | 🔴 No automated suite | Stale curl scripts, no pytest |
| **RLS** | 🟡 Built, not merged | Needs Railway prod access for NOBYPASSRLS |
| **Frontend** | 🟡 UX audit done, not implemented | Awaiting Olesia review |

**Single source of truth:** `docs/LexFlow_Agentic_Roadmap.json` (21 tasks, 53 kanban cards)

---

## 2. Gantt C workstream (current branch: `feat/gantt-c`)

### What's done
- ✅ Frappe-Gantt 1.2.2 vendored + checksum-verified (`static/vendor/frappe-gantt/1.2.2/`)
- ✅ Component scaffold (skeleton, no chart code)
- ✅ Integration approach documented
- ✅ P0–P4 prerequisite gates passed (with flags)
- ✅ M1 scaffold committed (`299c151`)
- ✅ M1 integration approach + gate report committed (`a6d8534`)

### What's blocking M2
| # | Blocker | Owner | Status |
|---|---|---|---|
| 1 | `GET /api/gantt/tasks` endpoint | Backend agent | Not started |
| 2 | Approved task start date (P2) | Olesia | ✅ Approved 2026-10-14 |
| 3 | Staff visibility rule (P3) | Olesia | Proposed, needs approval |
| 4 | Live Flask route smoke test | Any | Blocked (interpreter gate) |

### Next actions
1. **Olesia approves** the P3 staff visibility rule (proposed in `docs/gantt_gate_report.md` §P3)
2. **Backend agent** implements `/api/gantt/tasks` with exact whitelist + workspace scoping
3. **Backend agent** creates additive migration for `tasks.startdate DATE NULL`
4. **M1 formal approval** — cross-approve with non-free route (plan §12.7)
5. **M2** — implement `render()` in `gantt_view.js`, wire to real endpoint

---

## 3. Production outage (P0 blocker)

**Status:** `https://web-production-031a6.up.railway.app/` returns 404 (day 19)
**Root cause:** Railway edge has no active service bound to the domain
**Blocker:** Needs Olesia's Railway prod access (CLI token gets 403 on Backboard GraphQL)
**Not a code issue** — no roadmap task status change can fix this

**Kanban card `t_8cbc766e` is marked done** but production is still down — card status does not reflect reality.

---

## 4. Security gaps (from T-008 audit)

| ID | Severity | Issue | Effort |
|---|---|---|---|
| A1 | 🔴 CRITICAL | `/api/auth/seed` unprotected destructive endpoint | 0.5–1h |
| A2 | 🔴 CRITICAL | Hardcoded production creds re-seeded on boot | Force pw change |
| A3 | 🟡 HIGH | SECRET_KEY/JWT_SECRET_KEY fall back to dev key | Verify in Railway |
| A5 | 🟡 HIGH | RLS not merged (app-level filter only) | See T-014 |
| A6 | 🟡 MEDIUM | Task/calendar/intake reflection gaps | See T-002 |

**A1 + A2 are quick wins** — should be fixed immediately.

---

## 5. Test infrastructure

- **No pytest suite** — only stale curl scripts (`run_local_tests.sh`, `test_runner.sh`)
- Scripts hard-code `cd ~/Desktop/LexFlow/lexflow_hermes_v1` (path does not exist)
- **No baseline** — plan §14 P4 requires "baseline test suite passes" before Gantt

**Next action:** Create a minimal pytest suite with the 6 authorization tests from P3 + basic endpoint tests.

---

## 6. Agent roster

| Agent | Role | Status |
|---|---|---|
| operator_installer | Orchestration, deploy gate, infra, local testing | Active |
| backend_dev | Audit, RLS, API logic | Active |
| frontend_dev | UI implementation | On-call |
| lexflow_head_admin | Resend/email integration | Active |

**Coordination rules (from roadmap):**
- Cross-audit: operator ↔ backend code review before every test/deploy
- Report gate: every "fixed/done" must state LOCAL (preview link) or DEPLOYED (URL + commit hash)
- No deploy/push without Olesia's explicit go

---

## 7. Immediate asks for Olesia

1. **Railway prod access** — restore so the service can be rebound/restarted (P0 blocker)
2. **Approve P3 staff visibility rule** (proposed in `docs/gantt_gate_report.md`)
3. **Approve A1 security fix** (protect `/api/auth/seed`)
4. **Confirm flag naming:** `GANTT_VIEW_ENABLED` (read-only page) vs `GANTT_WRITE_ENABLED` (Layer 3, reserved)
5. **M1 formal approval** — or delegate to elected Owner

---

## 8. Task tracking

Active kanban cards: 53 (all unfinished tasks have exactly one open card)

| Column | Count |
|---|---|
| backlog | 10 |
| in_progress | 0 |
| blocked | 1 (T-014 RLS) |
| awaiting_confirmation | 4 |
| local_verified | 2 |
| done | 3 |
| deployed | 1 |

---

## 9. Coordination workflow going forward

1. **I track** all workstreams in this file + `docs/LexFlow_Agentic_Roadmap.json`
2. **I route** work to agents and track their outputs
3. **I enforce** gates — D1–D6 for Phase D, P0–P4 + M1–M6 for Gantt
4. **I stop** work that violates plan rules (concurrent writes, unscoped queries, free-model gate approval)
5. **I report** to Olesia at every gate

---

*This file is the single coordination hub. Update it as workstreams move.*
