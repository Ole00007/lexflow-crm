#!/usr/bin/env python3
"""Generate a self-contained Gantt demo HTML page with real roadmap data."""
import json

# Read vendor files
with open('static/vendor/frappe-gantt/1.2.2/frappe-gantt.css') as f:
    gantt_css = f.read()
with open('static/vendor/frappe-gantt/1.2.2/frappe-gantt.umd.js') as f:
    gantt_js = f.read()
with open('static/css/gantt/gantt.css') as f:
    lexflow_gantt_css = f.read()

# Real task data from the seed (21 roadmap tasks)
tasks = [
    {"id": 16, "name": "[T-016] A1 - LexFlow landing repoint (ab54f -> 031a6)", "start": "2026-08-28", "end": "2026-09-11", "progress": 100, "dependencies": "", "custom_class": "gantt-status-done"},
    {"id": 8, "name": "[T-008] Full read-only app audit + proactive improvement suggestions", "start": "2026-08-30", "end": "2026-09-27", "progress": 100, "dependencies": "", "custom_class": "gantt-status-done"},
    {"id": 7, "name": "[T-007] Contacts redesign: two-model split", "start": "2026-09-08", "end": "2026-09-29", "progress": 100, "dependencies": "", "custom_class": "gantt-status-done"},
    {"id": 19, "name": "[T-019] Design/UX audit: CRM + landing vs 2025 legal-SaaS standards", "start": "2026-09-19", "end": "2026-11-11", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 17, "name": "[T-017] SEAT_LIMIT_DEFAULT config value (5 seats/tenant)", "start": "2026-09-21", "end": "2026-10-28", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 15, "name": "[T-015] Uploads persistence (Railway Volume web-uploads)", "start": "2026-09-23", "end": "2026-11-11", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 1, "name": "[T-001] Intake page: manual name entry (remove autofill lock)", "start": "2026-09-27", "end": "2026-10-11", "progress": 100, "dependencies": "", "custom_class": "gantt-status-done"},
    {"id": 11, "name": "[T-011] Full inventory (all tenants: deploy platform, URLs, credentials)", "start": "2026-09-27", "end": "2026-11-11", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 10, "name": "[T-010] Resend email integration fact-check + test (Pagliano only)", "start": "2026-09-28", "end": "2026-11-04", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 2, "name": "[T-002] Cross-section data reflection (intake -> Contacts/Kanban/Calendar)", "start": "2026-10-06", "end": "2026-11-04", "progress": 50, "dependencies": "", "custom_class": "gantt-status-in-progress"},
    {"id": 3, "name": "[T-003] Conflict-check gate (legal-specific hard gate before engagement letter)", "start": "2026-10-27", "end": "2026-12-01", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 4, "name": "[T-004] Drip follow-up sequence (24h/72h/7d) with suppression rules", "start": "2026-10-30", "end": "2026-12-11", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 5, "name": "[T-005] WhatsApp Business API integration (client + avvocato notifications)", "start": "2026-11-02", "end": "2026-12-21", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 6, "name": "[T-006] Client portal notifications on case status change", "start": "2026-11-05", "end": "2026-11-26", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 9, "name": "[T-009] scheduled_actions table + Railway worker poll (event-driven delay engine)", "start": "2026-11-14", "end": "2026-12-26", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 12, "name": "[T-012] cl1-cl10 local mock test under Romanelli (full cycle)", "start": "2026-11-23", "end": "2026-12-21", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 13, "name": "[T-013] AI adaptive/reflective email agent (behavior-based follow-up)", "start": "2026-11-26", "end": "2026-12-31", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 14, "name": "[T-014] RLS merge (feat/rls branch)", "start": "2026-11-29", "end": "2027-01-10", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 18, "name": "[T-018] Agentic AI-personalized email automation spec", "start": "2026-12-11", "end": "2027-01-15", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 20, "name": "[T-020] i18n: CRM English -> Italian (+ Russian optional)", "start": "2026-12-17", "end": "2027-02-04", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
    {"id": 21, "name": "[T-021] Diagram view of task/case execution (n8n/Obsidian-graph style)", "start": "2026-12-20", "end": "2027-01-10", "progress": 0, "dependencies": "", "custom_class": "gantt-status-pending"},
]

tasks_json = json.dumps(tasks, indent=2)

html = '''<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>LexFlow Timeline — Gantt Demo</title>
    <style>
''' + gantt_css + '''
    </style>
    <style>
''' + lexflow_gantt_css + '''
    </style>
    <style>
        :root {
            --font-display: 'Instrument Serif', Georgia, serif;
            --font-body: 'Inter', system-ui, -apple-system, sans-serif;
            --text-xs: clamp(0.7rem, 1vw, 0.75rem);
            --text-sm: clamp(0.8rem, 1.2vw, 0.875rem);
            --text-base: clamp(0.9rem, 1.5vw, 1rem);
            --text-lg: clamp(1rem, 2vw, 1.125rem);
            --text-xl: clamp(1.1rem, 2.5vw, 1.25rem);
            --text-2xl: clamp(1.3rem, 3vw, 1.6rem);
            --text-3xl: clamp(1.8rem, 4vw, 2.6rem);
            --space-1: 0.25rem;--space-2:0.5rem;--space-3:0.75rem;--space-4:1rem;
            --space-6:1.5rem;--space-8:2rem;--space-10:2.5rem;--space-12:3rem;
            --radius-sm:6px;--radius-md:10px;--radius-lg:16px;--radius-xl:24px;--radius-full:9999px;
            --transition:180ms cubic-bezier(0.16,1,0.3,1);
        }
        [data-theme="dark"] {
            --bg:#0E1117;--surface:#161B27;--surface-2:#1E2535;--border:#1E2A3A;
            --text:#E2E8F0;--text-muted:#94A3B8;--text-faint:#7E90A9;
            --accent:#3B7DD8;--accent-h:#5A96F0;--accent-glow:rgba(59,125,216,0.2);
            --teal:#0F9B8E;--teal-h:#14B8A9;--success:#10B981;--warning:#F59E0B;
        }
        body { margin:0; min-height:100vh; font-family:var(--font-body); font-size:var(--text-base); line-height:1.65; color:var(--text); background:var(--bg); }
        .shell { display:flex; min-height:100vh; }
        .sidebar { width:240px; border-right:1px solid var(--border); padding:var(--space-4); display:flex; flex-direction:column; flex-shrink:0; background:var(--surface); }
        .brand { display:flex; align-items:center; gap:var(--space-2); font-size:var(--text-xl); font-weight:800; margin-bottom:var(--space-8); }
        .brand-mark { width:28px; height:28px; border-radius:var(--radius-md); display:grid; place-items:center; background:var(--accent); color:#fff; font-size:12px; font-weight:800; }
        .nav-label { font-size:var(--text-xs); font-weight:600; text-transform:uppercase; letter-spacing:.08em; color:var(--text-muted); margin-bottom:var(--space-2); }
        .nav-list { list-style:none; padding:0; margin:0; }
        .nav-link { display:flex; align-items:center; gap:var(--space-2); padding:var(--space-2) var(--space-3); border-radius:var(--radius-md); color:var(--text-muted); font-size:var(--text-sm); font-weight:500; text-decoration:none; }
        .nav-link:hover,.nav-link.active { background:var(--surface-2); color:var(--text); }
        .nav-dot { width:6px; height:6px; border-radius:50%; background:var(--accent); display:inline-block; }
        .main { flex:1; padding:var(--space-6); max-width:1200px; }
        .eyebrow { font-size:var(--text-xs); font-weight:700; text-transform:uppercase; letter-spacing:.1em; color:var(--accent); margin-bottom:var(--space-1); }
        h1 { font-family:var(--font-display); font-size:var(--text-3xl); font-weight:400; margin:0 0 var(--space-2); letter-spacing:-.02em; }
        .intro { color:var(--text-muted); margin:0 0 var(--space-6); max-width:600px; font-size:var(--text-sm); }
        .badge { display:inline-block; padding:2px 8px; border-radius:var(--radius-sm); font-size:var(--text-xs); font-weight:600; background:var(--accent-glow); color:var(--accent-h); }
        .gantt-page { display:flex; flex-direction:column; gap:var(--space-4); }
        .gantt-toolbar { display:flex; align-items:center; gap:var(--space-3); }
        .gantt-state { padding:var(--space-12); text-align:center; color:var(--text-muted); font-size:var(--text-lg); }
        .gantt-state--error { color:#EF4444; }
        .gantt-timeline { overflow-x:auto; border:1px solid var(--border); border-radius:var(--radius-lg); background:var(--surface); }
        .demo-banner { background:var(--surface-2); border:1px solid var(--border); border-radius:var(--radius-lg); padding:var(--space-4) var(--space-6); margin-bottom:var(--space-4); display:flex; align-items:center; gap:var(--space-3); }
        .demo-banner .badge { background:var(--accent); color:var(--bg); }
        .demo-banner p { margin:0; font-size:var(--text-sm); color:var(--text-muted); }
    </style>
</head>
<body>
    <div class="shell">
        <aside class="sidebar" aria-label="LexFlow workspace navigation">
            <a class="brand" href="#">
                <span class="brand-mark" aria-hidden="true">LF</span>
                LexFlow
            </a>
            <p class="nav-label">Workspace</p>
            <ul class="nav-list">
                <li><a class="nav-link" href="#">Dashboard</a></li>
                <li><a class="nav-link" href="#">Contacts</a></li>
                <li><a class="nav-link" href="#">Kanban <span class="nav-dot" aria-hidden="true"></span></a></li>
                <li><a class="nav-link" href="#">Calendar</a></li>
                <li><a class="nav-link" href="#">Tasks</a></li>
                <li><a class="nav-link active" href="#">📊 Timeline</a></li>
                <li><a class="nav-link" href="#">Matters</a></li>
                <li><a class="nav-link" href="#">Firm Team</a></li>
                <li><a class="nav-link" href="#">⚙ Settings</a></li>
                <li><a class="nav-link" href="#">Logout</a></li>
            </ul>
        </aside>
        <main class="main" id="main-content">
            <div class="demo-banner">
                <span class="badge">DEMO</span>
                <p><strong>LexFlow Timeline (Gantt)</strong> — 21 real roadmap tasks with dates. Read-only staff view. Data from <code>docs/LexFlow_Agentic_Roadmap.json</code>.</p>
            </div>
            <section class="gantt-page" aria-labelledby="gantt-heading">
                <div>
                    <p class="eyebrow">Internal staff · read-only</p>
                    <h1 id="gantt-heading">Timeline</h1>
                    <p class="intro">
                        Read-only task timeline. Bars reflect approved task dates and
                        status-derived progress; dates and progress cannot be edited here.
                    </p>
                </div>
                <div class="gantt-toolbar" role="group" aria-label="Timeline controls">
                    <span class="badge">Read-only</span>
                    <span class="badge">21 tasks</span>
                    <span class="badge">Frappe Gantt 1.2.2</span>
                </div>
                <div class="gantt-state" id="gantt-state-loading">Loading timeline…</div>
                <div class="gantt-state" id="gantt-state-empty" hidden>No tasks with both a start date and a due date to display.</div>
                <div class="gantt-state gantt-state--error" id="gantt-state-error" hidden>Could not load the timeline. Please retry.</div>
                <div class="gantt-state" id="gantt-state-denied" hidden>Please sign in to view the timeline.</div>
                <div class="gantt-timeline" id="gantt-timeline" tabindex="0" role="region" aria-label="Task timeline, horizontally scrollable">
                    <div id="gantt"></div>
                </div>
            </section>
        </main>
    </div>
    <script>
''' + gantt_js + '''
    </script>
    <script>
    (function() {
        'use strict';
        var GANTT_OPTIONS = {
            readonly: true,
            readonly_dates: true,
            readonly_progress: true,
            move_dependencies: false,
            view_mode: 'Day',
            view_mode_select: true,
            today_button: true,
            popup_on: 'click',
            infinite_padding: false,
            container_height: 'auto',
            bar_height: 30,
            padding: 18
        };

        var tasks = ''' + tasks_json + ''';

        // Hide loading, render chart
        var loadingEl = document.getElementById('gantt-state-loading');
        if (loadingEl) loadingEl.hidden = true;

        try {
            new Gantt('#gantt', tasks, GANTT_OPTIONS);
        } catch(e) {
            console.error('Gantt render failed', e);
            var errEl = document.getElementById('gantt-state-error');
            if (errEl) errEl.hidden = false;
        }
    })();
    </script>
</body>
</html>
'''

with open('docs/gantt/demo/gantt-demo.html', 'w') as f:
    f.write(html)

print(f"Created docs/gantt/demo/gantt-demo.html ({len(html)} bytes)")
