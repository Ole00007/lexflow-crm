# LexFlow T-005 — WhatsApp Business API Integration: Scoping Note

Date: 2026-10-06
Author: backend-dev (kanban card t_cba427b1)
Type: SCOPING / ANALYSIS ONLY — no code, no deploy, no external sends.
Status: conclusion recorded in `docs/LexFlow_Agentic_Roadmap.json` (T-005).

---

## 1. Current state (what exists today)

- `crm/notification_service.py` already has a hands-on WhatsApp path via **UltraMsg**
  (`send_whatsapp`, free tier `ultramsg` HTTP API, driven by `ULTRAMSG_INSTANCE_ID` + `ULTRAMSG_TOKEN`).
- Used today for: intake → workspace owner (`views.py:1056`), booking confirmations
  (`notify_client_and_owner` / `send_booking_notification`), owner+client on intake (best-effort, non-fatal).
- `crm/notification_service.py` also handles email: **Resend** by default with **SMTP fallback** preferred
  when `SMTP_HOST` is set (commit 5182bf8; T-010 fact-check).
- Email delivery to the client is currently BLOCKED in prod: `EMAIL_FROM=onboarding@resend.dev` only
  delivers to the account owner; Resend 403s on unverified domains (T-010). This matters because WhatsApp
  is often proposed as the *reliable* client channel — it is not a substitute for fixing email.

> **Flag for the decision:** UltraMsg is an **unofficial third-party API, NOT a Meta-endorsed Business
> Service Provider (BSP) and NOT the WhatsApp Business Platform**. The roadmap decision
> (`architecture_notes.automation_tech_decision.whatsapp`) specifies **Twilio or Meta Cloud API**.
> Whatever path we pick, the production code must move off UltraMsg. It can stay only as a
> local/dev fallback, never for real client or avvocato sends.

## 2. Provider decision: Meta Cloud API (direct) vs Twilio (BSP)

### Recommendation: **Meta Cloud API, integrated directly.**

Rationale for a legal-firm multi-tenant CRM at this volume:

| Criterion                | Meta Cloud API (direct)                          | Twilio (as BSP)                                |
|--------------------------|--------------------------------------------------|------------------------------------------------|
| Pricing base             | Meta category pricing only (utility ~€0.07-0.09 / msg, marketing higher, service-window replies free) | Meta category fees **+ Twilio per-message markup (~10-20%)** + number fee + account/platform fee |
| Platform fee             | None                                            | ~$20-40/mo depending on plan + $1.15/mo/number |
| 24h service window       | Free-form replies free inside 24h of user msg   | Same Meta window                                |
| Template approval        | Needed for business-initiated (first) contact   | Managed via Twilio console, still Meta-approved |
| Multi-channel (SMS etc.) | No (WhatsApp only)                              | Yes (optional cross-channel)                    |
| Onboarding/complexity    | Meta Business Verification + WABA + number + webhooks, self-service | Twilio console accelerates provisioning, more DX, extra layer |
| Right size here          | ✔ Low volume (a few firms × a handful of clients), zero platform fee, single-stack Flask | Cost + complexity overhead unjustified unless we need SMS cross-channel |

- **Why direct now:** volume is tiny (booking confirmations, case-status nudges, avvocato reminders). The
  per-message markup and monthly platform fee from a BSP does not earn back anything at this volume. Direct
  Cloud API keeps it a lightweight REST + webhook addition to the existing Flask service.
- **When to revisit Twilio/HubSpot-type BSP:** only if we adopt a second channel (SMS) or want managed
  number/template ops for many firms. Keep the notification layer provider-abstracted so swapping later is
  a one-module change.

### What direct integration requires (applies to any provider)
1. **Meta Business Portfolio + WhatsApp Business Account (WABA)** — business registration/verification
   (legal-firm documents; external, owned by Ole; allow ~1-3 weeks).
2. **A registered/verified WhatsApp Business number** per business (per-firm; ~€1-2/mo equivalent if on a
   BSP, effectively number cost direct too).
3. **A Facebook App + access token** + a webhook endpoint (we own it) for delivery/status callbacks.
4. **Approved message templates** for business-initiated (first-contact / marketing) messages; free-form
   only inside a 24h window after the user messages in.
5. **ECE/handling of EU data residency** — Meta Cloud API for EU businesses operates under EU standard
   contractual clauses / region processing; confirm the region setting at onboarding.

## 3. Consent / legal (GDPR + ePrivacy; EU context)

- WhatsApp outbound business messaging in the EU is governed by **GDPR (2016/679)** for personal-data
  processing **plus ePrivacy (Dir. 2002/58, transposed in Italy as Leg. Decree 196/2003 as amended)** for
  direct marketing messaging. **EAA (Law 11/2023)** is the accessibility act — out of scope for messaging
  itself (already covered by T-019 for the product UI).
- **Transactional / service messages** (booking confirmation, case-status change, avvocato task/deadline,
  hearing reminder, document-upload notice) do not need separate marketing consent — but they DO need a
  lawful basis (contract performance / legitimate interest) **and a clear opt-out / same-channel stop**.
- **Marketing / nurture WhatsApp** (e.g. drip follow-ups) requires **explicit, specific, informed,
  unambiguous opt-in**, recorded with **timestamp + source**, and an easy same-channel opt-out.
- Meta's own API policy independently **requires documented opt-in** to message a user — GDPR and Meta
  policy align here, so channel consent is a hard requirement regardless of provider choice.
- Data minimisation (Art. 5), retention limitation (Art. 5), right to erasure (Art. 17) apply to stored
  phone numbers — the existing single `contacts.phone` field must be exposable/deletable with the contact.

## 4. Opt-in storage (design)

Today `contacts` has only a monolithic `gdpr_consent (bool) + gdpr_consent_ts`. It does **not** distinguish
channels and has no provenance. Proposed additive columns on `contacts` (single-source-of-truth, §9 — extend,
do not fork a parallel registry):

- `wa_opt_in` — `Boolean, nullable=True`. `NULL` = not asked, `FALSE` = opted out / suppressed,
  `TRUE` = explicit channel opt-in.
- `wa_opt_in_ts` — timestamp.
- `wa_opt_in_source` — provenance: `intake` (LP checkbox) | `staff` (admin set for internal/seats) |
  `wa_reply` (user replied → Meta opt-in) | `import`.
- Keep `gdpr_consent` as the umbrella record; WhatsApp consent sits beside it, not replacing it.
- Avvocato/internal recipients (firm_team + user profiles) get a simpler `wa_opt_in` on their own record —
  staff consent to be notified is a workspace-admin decision, stored with the same pattern.

## 5. Suppression rules vs the existing email path

- **No suppression table exists today.** The roadmap `reflection_rules[].suppression` clauses
  (`"if replied"`, `"if replied or status changed"`, `"only_real_transitions"`, `"internal-only docs
  excluded"`, `conflict_map hard gate`) are descriptive prose, not enforced in code.
- Design the WhatsApp path to consume the **same suppression service** as email so the two channels never
  contradict each other: one `should_notify(contact, channel, notif_type)` gate used by both.
- Per-channel + global:
  - Global `wa_opt_in=false` blocks marketing/nurture WhatsApp but can still allow transactional if the
    contact engaged that case (channel-independent service rules).
  - A same-channel "STOP"/opt-out on WhatsApp must persist back to `wa_opt_in=false` and be honored
    immediately, mirroring email unsubscribe handling (which also does not yet exist — flag).
- Confirm **delivery status via webhooks** and don't re-send if the reply or the 24h window expires; align
  with reflection_rules timing (24h/72h/7d drip) so WhatsApp nudges and email follow-ups do not double-fire
  on the same slot.

## 6. Cost / seat implications

- **WhatsApp Business API has NO per-seat pricing.** Seats only matter for the CRM's own
  `SEAT_LIMIT_DEFAULT` (5/tenant, T-017) — independent of WhatsApp.
- Cost is per-message by category + number/verification:
  - Category matters: prefer **utility/service** templates (cheap, appropriate for legal ops) over
    **marketing** (more expensive, more intrusive, stricter).
  - Service-window replies (free-form within 24h) are effectively free.
  - Estimated monthly cost at current volume (a few firms × tens of messages): **single-digit €**, well
    under any per-seat or platform threshold. Number verification + business verification are the real
    cost (external time), not message volume.

## 7. Time & priority estimate

- **Effort: ~2-4 engineer-days (backend)**, broken as:
  - Migration: add opt-in columns (`contacts` + staff/user). (0.5 day)
  - Provider abstraction + Meta Cloud API client, template call + webhook handler. (1-1.5 days)
  - Suppression service shared with email + reflection-rule wiring; intake/contact UI to capture
    `wa_opt_in` + source. (1 day)
  - Template creation, test in sandbox, webhook delivery-status handling. (0.5-1 day)
- **External/blocking:** Meta business verification + number + template approval = **Ole + firm documents,
  ~1-3 weeks wall-clock**, and it requires a real target tenant (Pagliano/Romanelli) to verify against.
- **Priority recommendation: keep P2, keep column backlog.** It is parallel-safe (depends on nothing) but:
  (1) prod has been down 9 days (P0, day 9), so any WhatsApp integration cannot be tested/deployed to prod
  until that is resolved; (2) fixing email delivery (T-010 — verified Resend domain) is cheaper and should
  land first, because WhatsApp is a complementary channel, not the fix for broken email.
- **Suggested owner:** `backend_dev` (owns `notification_service.py`, RLS, API logic). Proposed as the
  assigned_agent for T-005.

## 8. Scope conclusion (recorded in roadmap JSON)

- Provider: **Meta Cloud API, integrated directly** (drop UltraMsg from prod path). Twilio/BSP only if we
  later add SMS or need managed onboarding for many firms.
- Consent: explicit, channel-specific `wa_opt_in` (+ts/source) stored on `contacts`; transactional vs
  marketing split under GDPDGR/ePrivacy; same-channel opt-out honored.
- Suppression: one shared `should_notify(contact, channel, type)` gate used by both email and WhatsApp;
  honor reflection_rules suppression + 24h window + delivery webhooks.
- Cost: per-message category pricing, no per-seat; single-digit €/mo at current volume; real cost is
  business verification (external).
- Priority: keep **P2 / backlog**; sequence after P0 prod-restore and T-010 email delivery fix.
- Owner: `backend_dev`.
- HARD GATE: no code, no deploy, no push, no external sends until Ole approves this scope.
