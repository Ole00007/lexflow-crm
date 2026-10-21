// sync-data.mjs — regenerate the DERIVED, read-only roadmap snapshot.
//
// AGENT_RULES §9 (single source of truth): the ONLY authority for LexFlow task
// status is docs/LexFlow_Agentic_Roadmap.json in the CRM repo. This script
// COPIES it into the app bundle as a *derived* artifact so the standalone app
// can ship/deploy without the repo. It is regenerated on every predev/prebuild,
// never hand-edited, and never written back to the authority. The derived copy
// is labelled with a `_derived` block at the top (§9.3).
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const AUTHORITY = resolve(here, '../../../docs/LexFlow_Agentic_Roadmap.json')
const OUT = resolve(here, '../src/data/lexflow-roadmap.generated.json')

if (!existsSync(AUTHORITY)) {
  console.error(`[sync-data] AUTHORITY not found at ${AUTHORITY}`)
  console.error('[sync-data] Keeping any existing derived snapshot; build will use last-known data.')
  process.exit(existsSync(OUT) ? 0 : 1)
}

const raw = readFileSync(AUTHORITY, 'utf8')
let parsed
try {
  parsed = JSON.parse(raw)
} catch (e) {
  console.error('[sync-data] authority JSON is malformed:', e.message)
  process.exit(1)
}

const derived = {
  _derived: {
    is_derived: true,
    note: 'DERIVED READ-ONLY COPY. Do not edit. Regenerated from the authority by scripts/sync-data.mjs.',
    authority: 'lexflow-crm/docs/LexFlow_Agentic_Roadmap.json',
    generated_at: new Date().toISOString(),
    authority_last_updated: parsed.last_updated ?? null,
  },
  ...parsed,
}

writeFileSync(OUT, JSON.stringify(derived, null, 2) + '\n', 'utf8')
console.log(
  `[sync-data] wrote derived snapshot -> src/data/lexflow-roadmap.generated.json ` +
  `(authority last_updated=${parsed.last_updated}, ${parsed.tasks?.length ?? 0} tasks)`
)
