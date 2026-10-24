// TaskDetail — right-side drawer. Read-only: nothing here mutates data.
export default function TaskDetail({ task, project, stage, onClose, onPick }) {
  const dependents = project.tasks.filter((t) => t.dependsOn.includes(task.id))
  return (
    <>
      <div className="drawer-bg" onClick={onClose} />
      <aside className="drawer">
        <button className="btn close" onClick={onClose}>✕ Close</button>
        <div className="gid" style={{ fontSize: 12 }}>{task.id}</div>
        <h2 style={{ textTransform: 'none', letterSpacing: 0, fontSize: 19, color: 'var(--text)', margin: '6px 0 2px' }}>{task.title}</h2>
        <span className="pill" style={{ background: stage.color, color: 'rgba(0,0,0,.75)', borderColor: 'transparent' }}>{stage.label}</span>

        <dl className="kv">
          <dt>Stage</dt><dd>{stage.label} ({Math.round(task.progress * 100)}%)</dd>
          {task.priority && (<><dt>Priority</dt><dd>{task.priority}</dd></>)}
          {task.agent && (<><dt>Owner</dt><dd>{task.agent}</dd></>)}
          {task.deployStatus && (<><dt>Deploy</dt><dd>{task.deployStatus}</dd></>)}
          {task.tags?.length > 0 && (<><dt>Scope</dt><dd>{task.tags.join(', ')}</dd></>)}
          <dt>Depends on</dt>
          <dd>{task.dependsOn.length ? task.dependsOn.map((d) => (
            <a key={d} href="#" onClick={(e) => { e.preventDefault(); onPick(d) }} style={{ marginRight: 8 }}>{d}</a>
          )) : '—'}</dd>
          <dt>Blocks</dt>
          <dd>{dependents.length ? dependents.map((d) => (
            <a key={d.id} href="#" onClick={(e) => { e.preventDefault(); onPick(d.id) }} style={{ marginRight: 8 }}>{d.id}</a>
          )) : '—'}</dd>
        </dl>

        {task.notes && <div className="notes">{task.notes}</div>}
      </aside>
    </>
  )
}
