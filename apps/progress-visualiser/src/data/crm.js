import { useEffect, useState } from 'react'

// Optional LIVE adapter. The standalone app's primary data is the derived
// roadmap snapshot (always available). This probes whether a live LexFlow CRM
// Gantt API is reachable — and is HONEST when it is not (prod is 404 as of the
// roadmap's open_p0; local server is JWT-gated). It never fabricates data.
//
// Configure a base via ?crm=<url> query param or VITE_CRM_BASE at build time.
const CRM_BASE =
  (typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('crm')) ||
  (import.meta.env?.VITE_CRM_BASE ?? '')

export function useLiveCrm() {
  const [state, setState] = useState({
    ok: false,
    label: CRM_BASE ? 'probing…' : 'offline (roadmap snapshot)',
    detail: CRM_BASE
      ? `Probing ${CRM_BASE}/api/gantt/tasks`
      : 'No live CRM configured. Rendering the read-only roadmap snapshot. Pass ?crm=<url> to probe a live server.',
  })

  useEffect(() => {
    if (!CRM_BASE) return
    let alive = true
    const url = `${CRM_BASE.replace(/\/$/, '')}/api/gantt/tasks`
    fetch(url, { headers: { Accept: 'application/json' } })
      .then((r) => {
        if (!alive) return
        if (r.status === 401 || r.status === 403) {
          setState({ ok: true, label: 'up (auth required)', detail: `${url} → ${r.status} (JWT-gated, server alive)` })
        } else if (r.ok) {
          setState({ ok: true, label: 'up', detail: `${url} → 200` })
        } else {
          setState({ ok: false, label: `down (${r.status})`, detail: `${url} → ${r.status}` })
        }
      })
      .catch((e) => {
        if (!alive) return
        setState({ ok: false, label: 'unreachable', detail: `${url} → ${e.message}` })
      })
    return () => { alive = false }
  }, [])

  return state
}
