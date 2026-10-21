// Pulse — the "progress is instantly obvious" hero surface.
function Ring({ pct }) {
  const r = 86, c = 2 * Math.PI * r
  const off = c * (1 - pct / 100)
  return (
    <div className="ring-wrap">
      <svg width="200" height="200" viewBox="0 0 200 200">
        <defs>
          <linearGradient id="pg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#6ea8fe" />
            <stop offset="100%" stopColor="#a855f7" />
          </linearGradient>
        </defs>
        <circle cx="100" cy="100" r={r} fill="none" stroke="var(--border)" strokeWidth="16" />
        <circle
          cx="100" cy="100" r={r} fill="none" stroke="url(#pg)" strokeWidth="16"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
          transform="rotate(-90 100 100)"
          style={{ transition: 'stroke-dashoffset .7s cubic-bezier(.2,.8,.2,1)' }}
        />
      </svg>
      <div className="ring-label">
        <div className="big">{pct}%</div>
        <div className="cap">weighted progress</div>
      </div>
    </div>
  )
}

export default function Pulse({ project, stats, onPick }) {
  const segs = project.stages
    .map((s) => ({ ...s, n: stats.byStage[s.key] || 0 }))
    .filter((s) => s.n > 0)

  // the "what moved" highlight: most-advanced completed items
  const wins = project.tasks.filter((t) => t.stage === 'deployed' || t.stage === 'done').slice(0, 4)

  return (
    <div className="grid" style={{ gap: 18 }}>
      <div className="card">
        <div className="pulse">
          <Ring pct={stats.weightedPct} />
          <div>
            <div className="metrics">
              <div className="metric"><div className="v">{stats.completed}/{stats.total}</div><div className="l">Completed</div></div>
              <div className="metric"><div className="v">{stats.completedPct}%</div><div className="l">Done &amp; shipped</div></div>
              <div className="metric"><div className="v" style={{ color: 'var(--accent)' }}>{stats.inFlight}</div><div className="l">In flight</div></div>
              <div className="metric"><div className="v" style={{ color: stats.blocked ? 'var(--bad)' : 'var(--text)' }}>{stats.blocked}</div><div className="l">Blocked</div></div>
            </div>
            <div style={{ marginTop: 18 }}>
              <div className="stagebar">
                {segs.map((s) => (
                  <div key={s.key} className="seg" title={`${s.label}: ${s.n}`}
                    style={{ flex: s.n, background: s.color }} />
                ))}
              </div>
              <div className="legend">
                {project.stages.map((s) => (
                  <div className="item" key={s.key}>
                    <span className="sw" style={{ background: s.color }} />
                    {s.label} <b style={{ color: 'var(--text)' }}>{stats.byStage[s.key] || 0}</b>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {wins.length > 0 && (
        <div className="card">
          <h2>✓ Progress landed — done &amp; shipped</h2>
          <div className="lanes" style={{ gridAutoColumns: 'minmax(220px, 1fr)' }}>
            {wins.map((t) => (
              <div className="tkt" key={t.id} style={{ borderLeftColor: 'var(--ok)' }} onClick={() => onPick(t.id)}>
                <div className="tid">{t.id}</div>
                <div className="tt">{t.title}</div>
                <div className="meta">
                  <span className="pill">{t.stage}</span>
                  {t.priority && <span className="pill">{t.priority}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
