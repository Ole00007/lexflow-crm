import { useMemo, useState, useEffect } from 'react'
import { PROJECTS, computeStats, stageByKey } from './data/model.js'
import Pulse from './components/Pulse.jsx'
import FlowBoard from './components/FlowBoard.jsx'
import TaskDetail from './components/TaskDetail.jsx'
import { useLiveCrm } from './data/crm.js'

export default function App() {
  const [projectId, setProjectId] = useState('lexflow')
  const [tab, setTab] = useState('pulse')
  const [selected, setSelected] = useState(null)
  const [theme, setTheme] = useState('dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const project = useMemo(() => PROJECTS.find((p) => p.id === projectId), [projectId])
  const stats = useMemo(() => computeStats(project), [project])
  const live = useLiveCrm()

  const selectedTask = selected ? project.tasks.find((t) => t.id === selected) : null

  return (
    <div className="app">
      <header className="hdr">
        <div className="brand">
          <div className="logo">▰</div>
          <div>
            <h1>Progress Visualiser</h1>
            <div className="sub">Make progress visible · LexFlow CRM as data base</div>
          </div>
        </div>
        <div className="spacer" />
        <span className="chip" title={live.detail}>
          <span className={`dot ${live.ok ? 'ok' : 'bad'}`} />
          Live CRM: {live.label}
        </span>
        <select className="select" value={projectId} onChange={(e) => { setProjectId(e.target.value); setSelected(null) }}>
          {PROJECTS.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <button className="btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
          {theme === 'dark' ? '☀ Light' : '☾ Dark'}
        </button>
      </header>

      <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 18, flexWrap: 'wrap' }}>
        <div className="tabs">
          <button className={`tab ${tab === 'pulse' ? 'active' : ''}`} onClick={() => setTab('pulse')}>Pulse</button>
          <button className={`tab ${tab === 'flow' ? 'active' : ''}`} onClick={() => setTab('flow')}>Flow / Gantt</button>
        </div>
        <span className="chip">
          Source: {project.source}
          {project.lastUpdated ? ` · updated ${project.lastUpdated}` : ''}
        </span>
      </div>

      {project.openP0?.length > 0 && (
        <div className="card p0" style={{ marginBottom: 18 }}>
          <h2>⚠ Open P0 — blocking production</h2>
          {project.openP0.map((p, i) => (
            <div key={i} style={{ fontSize: 13, lineHeight: 1.5 }}>
              <b>{p.id}</b> — {p.status}. <span style={{ color: 'var(--text-dim)' }}>{String(p.detail || '').slice(0, 220)}…</span>
            </div>
          ))}
        </div>
      )}

      {tab === 'pulse'
        ? <Pulse project={project} stats={stats} onPick={setSelected} />
        : <FlowBoard project={project} onPick={setSelected} />}

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          project={project}
          stage={stageByKey(project.stages, selectedTask.stage)}
          onClose={() => setSelected(null)}
          onPick={setSelected}
        />
      )}

      <div className="footer">
        Read-only visualiser · additive, no CRM model or migration changed · the LexFlow dataset is a
        <b> derived</b> snapshot of <code>docs/LexFlow_Agentic_Roadmap.json</code> (the single authority) —
        regenerated at build, never written back. The in-CRM Frappe Gantt is roadmap <b>T-021</b> (separate deliverable).
      </div>
    </div>
  )
}
