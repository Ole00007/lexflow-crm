import { stageByKey } from '../data/model.js'

// FlowBoard — two honest readings of "how far has it progressed":
//   1. Swimlane: kanban-by-stage. What is done / in progress / blocked / next.
//   2. Progress Gantt: one row per task; the x-axis is % COMPLETION, not time
//      (the roadmap has no dates — we never invent them). A bar fills to the
//      task's stage weight; blocked/milestone items render as a diamond.

function topoOrder(tasks) {
  const byId = Object.fromEntries(tasks.map((t) => [t.id, t]))
  const seen = new Set(), out = []
  const visit = (t, guard = new Set()) => {
    if (seen.has(t.id) || guard.has(t.id)) return
    guard.add(t.id)
    for (const d of t.dependsOn) if (byId[d]) visit(byId[d], guard)
    seen.add(t.id); out.push(t)
  }
  for (const t of tasks) visit(t)
  return out
}

export default function FlowBoard({ project, onPick }) {
  const ordered = topoOrder(project.tasks)

  return (
    <div className="grid" style={{ gap: 18 }}>
      <div className="card">
        <h2>Flow — by stage</h2>
        <div className="lanes">
          {project.stages.map((s) => {
            const items = project.tasks.filter((t) => t.stage === s.key)
            return (
              <div className="lane" key={s.key}>
                <h3><span className="sw" style={{ width: 9, height: 9, borderRadius: 3, background: s.color }} /> {s.label}</h3>
                <div className="cnt">{items.length} item{items.length === 1 ? '' : 's'}</div>
                {items.map((t) => (
                  <div className="tkt" key={t.id} style={{ borderLeftColor: s.color }} onClick={() => onPick(t.id)}>
                    <div className="tid">{t.id}</div>
                    <div className="tt">{t.title}</div>
                    <div className="meta">
                      {t.priority && <span className="pill">{t.priority}</span>}
                      {t.dependsOn.length > 0 && <span className="pill">↳ {t.dependsOn.join(', ')}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>

      <div className="card">
        <h2>Progress Gantt — x-axis is completion %, not time (dateless by design)</h2>
        <div className="gaxis"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div>
        <div className="gantt">
          {ordered.map((t) => {
            const st = stageByKey(project.stages, t.stage)
            const pct = Math.round(t.progress * 100)
            const isMilestone = t.stage === 'blocked' || t.stage === 'backlog'
            return (
              <div className="grow" key={t.id}>
                <div className="gname" onClick={() => onPick(t.id)} title={t.title}>
                  <span className="gid">{t.id}</span>
                  <span className="gtitle">{t.title}</span>
                </div>
                <div className="gtrack">
                  {isMilestone ? (
                    <span className="gdot" style={{ left: `${Math.max(pct, 2)}%`, background: st.color }}
                      title={`${st.label} · ${pct}%`} />
                  ) : (
                    <div className="gbar" style={{ width: `${Math.max(pct, 7)}%`, background: st.color }}>
                      <span className="st">{st.label} · {pct}%</span>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 10 }}>
          Diamonds = backlog/blocked (no forward progress yet). Bars fill to the stage's completion weight.
          Dependencies come from the roadmap's <code>depends_on</code> and order the rows top-to-bottom.
        </div>
      </div>
    </div>
  )
}
