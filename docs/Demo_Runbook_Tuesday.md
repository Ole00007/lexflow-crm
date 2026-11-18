# Demo runbook — LexFlow + Elisa, Tuesday 2026-11-24

Audience: Avv. Tommaso Ferro. Demo runs on **Ole's localhost**, not production.

---

## 0. Five minutes before

```bash
# 1. one server, one owner (port-5057 lock)
cd ~/projects/lexflow/lexflow-crm-wt-integration
~/projects/.locks/lockctl.sh take port-5057 smoothy_op_dir "demo"

# 2. start (template auto-reload is ON; only Python changes need a restart)
./run_demo.sh          # or the command in section 6

# 3. golden smoke — must print RESULT: PASS
./local_venv/bin/python scripts/demo_smoke.py --base http://127.0.0.1:5057
```

If smoke fails, **do not improvise in front of the client** — use the fallback in section 5.

## 1. What to open

`http://127.0.0.1:5057/mindmap` — logged in as `olesya00007@yahoo.com` (superadmin).

## 2. The script (7 minutes)

| # | Do this | Say this |
|---|---|---|
| 1 | Open **Mindmap**. Point at the first card. | "Every note shows who wrote it, when, and what it belongs to." |
| 2 | Change **Source** to `Human`, Apply. | "These are the firm's notes. Nothing else can write here." |
| 3 | Change **Source** to `Agent`. | "The agent's own words never enter this record — only drafts you accepted." |
| 4 | Point at the **draft tray** on the right. | "Elisa proposes, she does not act. Each proposal carries its reason and an expiry." |
| 5 | Press **Accept** on one draft. | "Accepting promotes it into the record, marked as an Elisa draft, and keeps the author." |
| 6 | Press **Reject** on the other. | "Rejected proposals stay in the audit trail, never in the record." |
| 7 | Ask Elisa in the chat bubble: "create task Send filing receipt for matter Rasing separazione due in 3 days". | "She cannot write on her own — she raises an approval. I confirm, and only then does it exist." |
| 8 | (Governance) Settings → kill switch ON. Back to Mindmap, refresh. | "One switch stops all background proposals for this workspace, immediately." |

## 3. What NOT to show

- Do **not** mention email/WhatsApp sending — the domain is unverified and outbound is disabled by design.
- Do **not** open production (`web-production-031a6`) — Elisa is intentionally dormant there (404).
- Do **not** demo the ROI/calendar work — it is not part of this build.

## 4. If the client asks "can it write anywhere else?"

Answer: agent output exists only in `agent_drafts`. The `notes` table has no
agent-writable path; promotion is a human action. That is a database-level
guarantee, not a setting.

## 5. Fallback

If the server or a call fails:

1. `./local_venv/bin/python scripts/demo_smoke.py` → read the FAIL line; it names the broken step.
2. If it is a data problem, reseed: `python seed_mindmap_notes.py && python seed_mindmap_demo.py --workspace lexflow`.
3. If it is a code problem, switch to screenshots in `docs/`: `mindmap-ui-1440.png`,
   `mindmap-ui-390.png` (already generated), and continue the conversation from there.
4. Never restart the server while the client is watching — ask for 30 seconds.

## 6. Server command

```bash
cd ~/projects/lexflow/lexflow-crm-wt-integration
DATABASE_URL="sqlite:///$HOME/.hermes/profiles/smoothy_op_dir/cache/scratch/mindmap_demo.db" \
LEXFLOW_VAULT_DIR="$HOME/.hermes/profiles/smoothy_op_dir/cache/scratch/demo_vault" \
AGENT_ENABLED=1 SECRET_KEY=local-demo-secret-key-for-dev-only-32b \
JWT_SECRET_KEY=local-demo-jwt-secret-key-for-dev-only-32b \
./local_venv/bin/python ~/.hermes/profiles/smoothy_op_dir/cache/scratch/mindmap_boot_5057.py
```

## 7. After the demo

- Release the lock: `~/projects/.locks/lockctl.sh release port-5057 smoothy_op_dir`
- Record what the client asked for in the project note (currently Italian, non-binding).
