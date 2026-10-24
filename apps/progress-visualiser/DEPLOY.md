# Deployment plan — Progress Visualiser (PREPARED, NOT EXECUTED)

> **Do NOT run any of this without Ole's explicit per-deploy authorization** (AGENT_RULES §11.5 push
> gate + §10 deploy gate). This file is a plan for Ole to approve. No secrets are stored here —
> only references. The app is a **static SPA** (`vite build` → `dist/`), so both targets serve the
> same immutable `dist/` artifact.

Build artifact (both targets):
```bash
cd apps/progress-visualiser
npm ci
npm run build        # runs prebuild sync-data, emits ./dist  (index.html + assets/, ~57 kB gz)
```

---

## Option A — Cloudflare Workers (Static Assets)

Config is committed as `wrangler.toml`. Workers' native static-assets binding serves `dist/` with
SPA fallback — no separate Pages project required.

**Prereqs:** a Cloudflare account + `CLOUDFLARE_API_TOKEN` (reference only — set in the shell/CI env
or `wrangler login`; never commit it). `npm i -g wrangler` or `npx wrangler`.

**Deploy (after Ole's go):**
```bash
cd apps/progress-visualiser
npm run build
npx wrangler deploy          # reads wrangler.toml, uploads ./dist
```

**Route / custom domain:** add a `route` or `custom_domain` in `wrangler.toml` once Ole picks the
hostname (e.g. `progress.lexflow.<domain>`). Default is the `*.workers.dev` subdomain.

**Secrets by reference:** none required — the app ships the derived roadmap snapshot and needs no
server secret. If live CRM probing is wanted in prod, set a **public** base at build time:
`VITE_CRM_BASE=https://<crm-host> npm run build` (it is a public URL, not a secret).

**Rollback:** `npx wrangler rollback` (previous deployment), or `npx wrangler deployments list` then
`npx wrangler rollback --message "…" <deployment-id>`. Workers keeps prior versions.

---

## Option B — Railway (static web service)

Serve `dist/` with any static server. Committed files: `railway.json` (build/deploy) and a minimal
`serve` start command.

**Prereqs:** Railway project + `RAILWAY_TOKEN` (reference only). `npm i -g @railway/cli` or `npx`.

**Deploy (after Ole's go):**
```bash
cd apps/progress-visualiser
railway up                   # uses railway.json: build = npm ci && npm run build; start = npx serve dist -l $PORT
```
or point a Railway service at the repo subdirectory `apps/progress-visualiser` with:
- Build: `npm ci && npm run build`
- Start: `npx serve -s dist -l $PORT`   (`-s` = SPA fallback; `$PORT` injected by Railway)

**Route:** Railway assigns `*.up.railway.app`; attach a custom domain in the dashboard once chosen.

**Rollback:** Railway dashboard → Deployments → "Rollback" to the prior build, or
`railway deployment list` + redeploy the previous commit.

---

## Notes / gates
- **No new paid service** is provisioned without Ole's approval. Both targets have free tiers adequate
  for a static SPA.
- **No push** of this branch to a deploy-triggering branch without Ole's explicit go (§11.5).
- The production LexFlow CRM is currently **down (404, roadmap `open_p0`)**; this app does **not**
  depend on it to render (it uses the derived snapshot). Live probing degrades gracefully.
- **NOT VERIFIED:** neither deploy target has been executed or smoke-tested remotely — this is a plan.
