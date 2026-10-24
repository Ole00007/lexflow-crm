// model.js — the generic progress model + adapters.
//
// The whole point of this app: ANY human's project, from ANY tracker, is
// normalised into one shape (`Project`) so progress is visually obvious.
// Two adapters ship: the real LexFlow Agentic Roadmap, and a generic demo.

import roadmap from './lexflow-roadmap.generated.json'

// ---- Stage taxonomy -------------------------------------------------------
// `weight` = fraction of "done-ness" a task in this stage contributes (0..1).
// Planned vs actual stay distinguishable: weight is progress, not a date.
export const LEXFLOW_STAGES = [
  { key: 'backlog',               label: 'Backlog',        weight: 0.0,  color: '#5b6472' },
  { key: 'in_progress',           label: 'In progress',    weight: 0.4,  color: '#3b82f6' },
  { key: 'blocked',               label: 'Blocked',        weight: 0.1,  color: '#ef4444' },
  { key: 'awaiting_confirmation', label: 'Awaiting check', weight: 0.7,  color: '#f59e0b' },
  { key: 'local_verified',        label: 'Local verified', weight: 0.85, color: '#a855f7' },
  { key: 'deployed',              label: 'Deployed',       weight: 1.0,  color: '#10b981' },
  { key: 'done',                  label: 'Done',           weight: 1.0,  color: '#22c55e' },
]

// Generic synonym → canonical stage key, so arbitrary trackers normalise.
const GENERIC_STAGE_SYNONYMS = {
  todo: 'backlog', backlog: 'backlog', new: 'backlog', pending: 'backlog', not_started: 'backlog',
  doing: 'in_progress', in_progress: 'in_progress', wip: 'in_progress', active: 'in_progress', started: 'in_progress',
  blocked: 'blocked', stuck: 'blocked', on_hold: 'blocked',
  review: 'awaiting_confirmation', awaiting_confirmation: 'awaiting_confirmation', qa: 'awaiting_confirmation', testing: 'awaiting_confirmation',
  verified: 'local_verified', local_verified: 'local_verified', staged: 'local_verified',
  deployed: 'deployed', released: 'deployed', shipped: 'deployed',
  done: 'done', complete: 'done', completed: 'done', closed: 'done',
}

export function stageByKey(stages, key) {
  return stages.find((s) => s.key === key) || null
}

// ---- Progress stats -------------------------------------------------------
export function computeStats(project) {
  const stages = project.stages
  const byStage = Object.fromEntries(stages.map((s) => [s.key, 0]))
  let weighted = 0
  let completed = 0 // deployed or done
  for (const t of project.tasks) {
    if (byStage[t.stage] === undefined) byStage[t.stage] = 0
    byStage[t.stage] += 1
    weighted += t.progress
    if (t.stage === 'deployed' || t.stage === 'done') completed += 1
  }
  const n = project.tasks.length || 1
  return {
    total: project.tasks.length,
    completed,
    completedPct: Math.round((completed / n) * 100),
    weightedPct: Math.round((weighted / n) * 100),
    byStage,
    blocked: byStage.blocked || 0,
    inFlight: (byStage.in_progress || 0) + (byStage.awaiting_confirmation || 0) + (byStage.local_verified || 0),
  }
}

// ---- Adapter: LexFlow Agentic Roadmap ------------------------------------
export function lexflowProject() {
  const stageMap = Object.fromEntries(LEXFLOW_STAGES.map((s) => [s.key, s]))
  const tasks = (roadmap.tasks || []).map((t) => {
    const stage = stageMap[t.column] ? t.column : 'backlog'
    return {
      id: t.id,
      title: t.title || t.name || t.id,
      stage,
      progress: stageMap[stage].weight,
      priority: t.priority || null,
      agent: t.assigned_agent || null,
      dependsOn: Array.isArray(t.depends_on) ? t.depends_on : [],
      notes: t.notes || '',
      tags: t.tenant_scope || [],
      deployStatus: t.deploy_status || null,
    }
  })
  return {
    id: 'lexflow',
    name: roadmap.project || 'LexFlow MVP',
    source: 'LexFlow Agentic Roadmap (read-only authority)',
    sourceNote: roadmap._derived?.note || 'docs/LexFlow_Agentic_Roadmap.json',
    lastUpdated: roadmap.last_updated || roadmap._derived?.authority_last_updated || null,
    generatedAt: roadmap._derived?.generated_at || null,
    openP0: roadmap.open_p0 || [],
    stages: LEXFLOW_STAGES,
    tasks,
  }
}

// ---- Adapter: generic demo project ("any human's project") ---------------
// Proves the visualiser is NOT LexFlow-specific. Fictional, dateless, safe.
const DEMO_RAW = {
  project: 'Launch my personal blog',
  last_updated: '2026-10-20',
  tasks: [
    { id: 'B-1', title: 'Pick a name + buy the domain', column: 'done', depends_on: [] },
    { id: 'B-2', title: 'Choose the publishing platform', column: 'done', depends_on: ['B-1'] },
    { id: 'B-3', title: 'Design the homepage', column: 'deployed', depends_on: ['B-2'] },
    { id: 'B-4', title: 'Write the first 3 posts', column: 'in_progress', depends_on: ['B-2'] },
    { id: 'B-5', title: 'Set up the newsletter', column: 'awaiting_confirmation', depends_on: ['B-3'] },
    { id: 'B-6', title: 'Hook up analytics', column: 'blocked', depends_on: ['B-3'] },
    { id: 'B-7', title: 'Record the launch video', column: 'backlog', depends_on: ['B-4'] },
    { id: 'B-8', title: 'Announce on socials', column: 'backlog', depends_on: ['B-4', 'B-5'] },
  ],
}

export function demoProject() {
  const stageMap = Object.fromEntries(LEXFLOW_STAGES.map((s) => [s.key, s]))
  const tasks = DEMO_RAW.tasks.map((t) => {
    const canon = GENERIC_STAGE_SYNONYMS[t.column] || 'backlog'
    const stage = stageMap[canon] ? canon : 'backlog'
    return {
      id: t.id,
      title: t.title,
      stage,
      progress: stageMap[stage].weight,
      priority: null,
      agent: null,
      dependsOn: t.depends_on || [],
      notes: '',
      tags: [],
      deployStatus: null,
    }
  })
  return {
    id: 'demo',
    name: DEMO_RAW.project,
    source: 'Demo dataset (fictional — proves genericity)',
    sourceNote: 'Bundled example to show the visualiser works for any project.',
    lastUpdated: DEMO_RAW.last_updated,
    generatedAt: null,
    openP0: [],
    stages: LEXFLOW_STAGES,
    tasks,
  }
}

export const PROJECTS = [lexflowProject(), demoProject()]
