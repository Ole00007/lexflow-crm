# Mindmap + Agent Draft Sandbox — API contract (v1, 2026-11-18)

**Status:** frozen for the Tuesday demo build. Backy builds the server; Fronty builds the UI
against this document only. Any change here must be announced to both before code changes.

**Base:** `/api` · **Auth:** JWT (existing `Authorization: Bearer …`) · **Scope:** every row is
`workspace_id`-scoped via `workspace_filter`; superadmin bypasses, nobody else does.

---

## 1. Invariants (non-negotiable)

1. `notes` is the **human** record. A person writing through `POST /api/notes` always produces
   `source='human'`. The route ignores client-supplied `source`/`source_ref`.
2. Agents write **only** to `agent_drafts`. There is no agent-writable path into `notes`;
   the only bridge is a human accepting a draft.
3. `require_review` is always true. No auto-promotion, no bulk approve.
4. Accept is **single-use and atomic**: `UPDATE … SET status='accepted' WHERE id=:id AND status='proposed'`;
   affected rows must be 1, else `409`.
5. A draft can only be accepted by `requested_by` (when set) or a superadmin in the same workspace.
6. Drafts expire: `expires_at` passed → `410 Gone` on accept, row stays for audit.
7. Max `max_per_day` (default 3) drafts per `(workspace, target_type, target_id)` per day.

---

## 2. Data model

### `agent_drafts`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `workspace_id` | int FK workspaces.id, not null, indexed | tenant scope |
| `target_type` | varchar(50) | `workspace` \| `task` \| `case` \| `contact` |
| `target_id` | int | |
| `content` | text | what the agent proposes |
| `origin` | varchar(20) | `human_request` \| `superior_agent` \| `event_rule` |
| `requested_by` | int FK users.id, nullable | set for `human_request` / `superior_agent` |
| `requested_by_agent` | varchar(64), nullable | e.g. `elisa`, `pa-orchestrator` |
| `evidence` | text, nullable | why the agent proposes this (observations, not confidence) |
| `status` | varchar(16) | `draft` \| `proposed` \| `accepted` \| `rejected` \| `expired` |
| `policy_id` | int FK agent_policies.id, nullable | set for `event_rule` |
| `expires_at` | datetime, not null | default now + 7d |
| `decided_by` | int FK users.id, nullable | |
| `decided_at` | datetime, nullable | |
| `note_id` | int FK notes.id, nullable | set on promotion |
| `created_at`, `updated_at` | datetime | |

### `agent_policies`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `workspace_id` | int FK, not null, indexed | |
| `event_key` | varchar(64) | `lead_stalled`, `quote_sent`, `deadline_missed`, `task_overdue`, `custom` |
| `enabled` | bool, default false | |
| `require_review` | bool, default true, **must stay true** | |
| `max_per_day` | int, default 3 | |
| `created_at`, `updated_at` | datetime | |
| unique | `(workspace_id, event_key)` | |

### `agent_delegations`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `workspace_id` | int FK, not null, indexed | |
| `from_user_id` | int FK users.id, not null | the human granting |
| `to_agent` | varchar(64), not null | e.g. `personal-assistant` |
| `scope` | text | JSON: `{"target_types":["task"],"target_ids":[12]}` or `"*"` |
| `expires_at` | datetime, not null | |
| `revoked_at` | datetime, nullable | |
| `created_at` | datetime | |

Migration: new revision off `n6d7e8f9a0b1`, additive only, `batch_alter_table` for SQLite.
Boot guard: add `db.create_all()` handles new tables automatically; no column ALTERs needed.

---

## 3. Endpoints

### Drafts
`GET /api/agent/drafts?status=proposed&target_type=task&target_id=12`
→ `200 [{id, workspace_id, target_type, target_id, content, origin, requested_by,
requested_by_agent, evidence, status, expires_at, created_at, note_id}]`

`POST /api/agent/drafts/<id>/accept`
→ `200 {draft: {...status:'accepted', note_id: N}, note: {...source:'agent', source_ref:'<id>'}}`
→ `403` not your draft · `409` already resolved · `410` expired · `404` not found

`POST /api/agent/drafts/<id>/reject`
→ `200 {draft: {... status:'rejected'}}`; same 403/409/410 rules.

`POST /api/agent/drafts` — **internal/agent path only**, never called from the browser.
Requires service identity header `X-Agent-Name: elisa` and an active policy or delegation;
rejects browser-origin calls. Body: `{target_type,target_id,content,origin,evidence}`.
→ `201` draft · `403` no policy/delegation · `429` daily cap hit.

**Promotion side-effect (server, not the client):**
insert `notes` row with `source='agent'`, `source_ref=str(draft.id)`,
`author_id=draft.requested_by`, `content=draft.content`, same workspace/target;
`activity_log` row `action='agent_draft_promoted'`, `actor_id` = approver.

### Policies
`GET /api/agent/policies` (any workspace member) → list
`PUT /api/agent/policies/<event_key>` (superadmin) body `{enabled, max_per_day}` → upsert.
`POST /api/agent/policies/kill-switch` (superadmin) body `{enabled:true|false}` → disables all
`event_rule` generation in the workspace immediately.

### Delegations
`GET /api/agent/delegations` · `POST /api/agent/delegations`
`{to_agent, scope, ttl_hours}` · `DELETE /api/agent/delegations/<id>` (revoke, sets `revoked_at`).
Only `from_user_id == caller` or superadmin may create/revoke.

---

## 4. UI contract (Fronty)

**Mindmap surface** (`/mindmap` or a Mindmap tab inside the existing project page):
- Note stream: `GET /api/notes/?target_type=workspace&target_id=<ws>` plus task/case tabs.
- Each card shows: author (`author_name` or `author_email`, fallback "system"), relative time,
  `source` chip (`Human` / `Elisa draft`), target label.
- Filter bar: source (All/Human/Agent), author, date from/to, free text (`q`), target type.
- Composer: textarea → `POST /api/notes/`.
- **Never** render a send/email action. Promoted notes are labelled "for review".

**Draft tray** (right rail or collapsible panel, visible only when `status=proposed` count > 0):
- Per draft: origin badge, evidence line, accept / reject buttons, expiry countdown.
- Accept → `POST /api/agent/drafts/<id>/accept`, then refresh stream and tray.
- Reject → `POST /api/agent/drafts/<id>/reject`.
- No "approve all" control.
- Empty state: "No drafts waiting for review."

**Kill switch**: superadmin-only toggle in settings; must call the policies kill-switch endpoint.

---

## 5. Demo script (Tuesday, localhost)

1. Open project → Mindmap: human note from Ole, chip shows **Human** + his name + time.
2. Filter `source=Agent` → empty (proves agents cannot write here).
3. Open draft tray → 2 seeded drafts from Elisa with evidence.
4. Accept one → it appears in the stream as **Elisa draft**, author preserved, `source_ref` set.
5. Reject the other → tray empties, audit row exists.
6. Toggle kill switch → new drafts stop; tray stays empty.

Seed command (Backy): `python seed_mindmap_demo.py --workspace lexflow` creating 2 drafts
(one task note, one project note) and no notes.
