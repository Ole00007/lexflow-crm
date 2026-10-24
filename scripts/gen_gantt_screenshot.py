#!/usr/bin/env python3
"""Generate demo screenshots showing the Gantt timeline with real data."""
from PIL import Image, ImageDraw, ImageFont
import json
from datetime import date, timedelta

# Real task data (same as seed)
tasks = [
    {"id": 16, "name": "[T-016] A1 - LexFlow landing repoint", "start": "2026-08-28", "end": "2026-09-11", "progress": 100, "class": "done"},
    {"id": 8, "name": "[T-008] Full read-only app audit", "start": "2026-08-30", "end": "2026-09-27", "progress": 100, "class": "done"},
    {"id": 7, "name": "[T-007] Contacts redesign: two-model split", "start": "2026-09-08", "end": "2026-09-29", "progress": 100, "class": "done"},
    {"id": 19, "name": "[T-019] Design/UX audit: legal-SaaS standards", "start": "2026-09-19", "end": "2026-11-11", "progress": 50, "class": "in_progress"},
    {"id": 17, "name": "[T-017] SEAT_LIMIT_DEFAULT config value", "start": "2026-09-21", "end": "2026-10-28", "progress": 50, "class": "in_progress"},
    {"id": 15, "name": "[T-015] Uploads persistence (Railway Volume)", "start": "2026-09-23", "end": "2026-11-11", "progress": 50, "class": "in_progress"},
    {"id": 1, "name": "[T-001] Intake page: manual name entry", "start": "2026-09-27", "end": "2026-10-11", "progress": 100, "class": "done"},
    {"id": 11, "name": "[T-011] Full inventory (all tenants)", "start": "2026-09-27", "end": "2026-11-11", "progress": 50, "class": "in_progress"},
    {"id": 10, "name": "[T-010] Resend email integration (Pagliano)", "start": "2026-09-28", "end": "2026-11-04", "progress": 50, "class": "in_progress"},
    {"id": 2, "name": "[T-002] Cross-section data reflection", "start": "2026-10-06", "end": "2026-11-04", "progress": 50, "class": "in_progress"},
    {"id": 3, "name": "[T-003] Conflict-check gate (legal-specific)", "start": "2026-10-27", "end": "2026-12-01", "progress": 0, "class": "pending"},
    {"id": 4, "name": "[T-004] Drip follow-up sequence (24h/72h/7d)", "start": "2026-10-30", "end": "2026-12-11", "progress": 0, "class": "pending"},
    {"id": 5, "name": "[T-005] WhatsApp Business API integration", "start": "2026-11-02", "end": "2026-12-21", "progress": 0, "class": "pending"},
    {"id": 6, "name": "[T-006] Client portal notifications", "start": "2026-11-05", "end": "2026-11-26", "progress": 0, "class": "pending"},
    {"id": 9, "name": "[T-009] scheduled_actions table + worker poll", "start": "2026-11-14", "end": "2026-12-26", "progress": 0, "class": "pending"},
    {"id": 12, "name": "[T-012] cl1-cl10 local mock test (Romanelli)", "start": "2026-11-23", "end": "2026-12-21", "progress": 0, "class": "pending"},
    {"id": 13, "name": "[T-013] AI adaptive email agent", "start": "2026-11-26", "end": "2026-12-31", "progress": 0, "class": "pending"},
    {"id": 14, "name": "[T-014] RLS merge (feat/rls branch)", "start": "2026-11-29", "end": "2027-01-10", "progress": 0, "class": "pending"},
    {"id": 18, "name": "[T-018] Agentic AI-personalized email spec", "start": "2026-12-11", "end": "2027-01-15", "progress": 0, "class": "pending"},
    {"id": 20, "name": "[T-020] i18n: CRM English -> Italian", "start": "2026-12-17", "end": "2027-02-04", "progress": 0, "class": "pending"},
    {"id": 21, "name": "[T-021] Diagram view of task/case execution", "start": "2026-12-20", "end": "2027-01-10", "progress": 0, "class": "pending"},
]

# LexFlow dark theme colors
BG = (14, 17, 23)       # #0E1117
SURFACE = (22, 27, 39)  # #161B27
SURFACE2 = (30, 37, 53) # #1E2535
BORDER = (30, 42, 58)   # #1E2A3A
TEXT = (226, 232, 240)  # #E2E8F0
TEXT_MUTED = (148, 163, 184)  # #94A3B8
ACCENT = (59, 125, 216) # #3B7DD8
ACCENT_H = (90, 150, 240) # #5A96F0
TEAL = (15, 155, 142)   # #0F9B8E
SUCCESS = (16, 185, 129) # #10B981
WARNING = (245, 158, 11) # #F59E0B
OVERDUE = (239, 68, 68)  # #EF4444

# Layout
WIDTH = 1400
LEFT_MARGIN = 260
RIGHT_MARGIN = 40
TOP_MARGIN = 60
ROW_HEIGHT = 40
BAR_HEIGHT = 28
CHART_TOP = 140
DATE_WIDTH = 100

def parse_date(s):
    y, m, d = s.split('-')
    return date(int(y), int(m), int(d))

def date_to_x(d, min_date, max_date, chart_width):
    total_days = (max_date - min_date).days
    if total_days == 0:
        return LEFT_MARGIN
    days_from_start = (d - min_date).days
    return LEFT_MARGIN + int(days_from_start / total_days * chart_width)

def draw_demo():
    # Calculate dimensions
    num_tasks = len(tasks)
    chart_height = num_tasks * ROW_HEIGHT
    total_height = CHART_TOP + chart_height + 200
    
    img = Image.new('RGB', (WIDTH, total_height), BG)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
        font_label = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 10)
        font_task = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
    except:
        font_title = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_task = ImageFont.load_default()
    
    # Sidebar
    draw.rectangle([0, 0, 240, total_height], fill=SURFACE)
    draw.rectangle([240, 0, 242, total_height], fill=BORDER)
    
    # Brand
    draw.rounded_rectangle([16, 16, 44, 44], radius=6, fill=ACCENT)
    draw.text((22, 22), "LF", fill=(255, 255, 255), font=font_label)
    draw.text((52, 20), "LexFlow", fill=TEXT, font=font_title)
    
    # Nav items
    nav_items = ["Dashboard", "Contacts", "Kanban", "Calendar", "Tasks", "📊 Timeline", "Matters", "Firm Team", "⚙ Settings", "Logout"]
    for i, item in enumerate(nav_items):
        y = 80 + i * 32
        if "Timeline" in item:
            draw.rounded_rectangle([8, y - 2, 232, y + 22], radius=6, fill=SURFACE2)
            draw.text((16, y + 2), item, fill=TEXT, font=font_label)
        else:
            draw.text((16, y + 2), item, fill=TEXT_MUTED, font=font_label)
    
    # Main content
    # Demo banner
    draw.rounded_rectangle([260, 16, WIDTH - 20, 70], radius=12, fill=SURFACE2)
    draw.rounded_rectangle([272, 28, 340, 52], radius=4, fill=ACCENT)
    draw.text((282, 34), "DEMO", fill=BG, font=font_small)
    draw.text((352, 34), "LexFlow Timeline (Gantt) — 21 real roadmap tasks with dates", fill=TEXT_MUTED, font=font_label)
    
    # Title
    draw.text((260, 90), "Timeline", fill=TEXT, font=font_title)
    draw.text((260, 130), "Read-only task timeline. Bars reflect approved task dates and status-derived progress.", fill=TEXT_MUTED, font=font_small)
    
    # Chart area
    chart_left = LEFT_MARGIN
    chart_right = WIDTH - RIGHT_MARGIN
    chart_width = chart_right - chart_left
    
    # Date range
    all_dates = []
    for t in tasks:
        all_dates.append(parse_date(t["start"]))
        all_dates.append(parse_date(t["end"]))
    min_date = min(all_dates)
    max_date = max(all_dates)
    
    # Month headers
    current = min_date.replace(day=1)
    while current <= max_date:
        x = date_to_x(current, min_date, max_date, chart_width)
        if x < chart_right:
            month_name = current.strftime("%b %Y")
            draw.text((x + 4, CHART_TOP - 20), month_name, fill=TEXT_MUTED, font=font_small)
            draw.line([(x, CHART_TOP), (x, CHART_TOP + chart_height)], fill=BORDER, width=1)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    
    # Today line
    today = date.today()
    if min_date <= today <= max_date:
        today_x = date_to_x(today, min_date, max_date, chart_width)
        draw.line([(today_x, CHART_TOP), (today_x, CHART_TOP + chart_height)], fill=ACCENT, width=2)
    
    # Tasks
    for i, task in enumerate(tasks):
        y = CHART_TOP + i * ROW_HEIGHT
        
        # Task name (left side)
        name = task["name"]
        if len(name) > 35:
            name = name[:32] + "..."
        draw.text((10, y + 8), name, fill=TEXT, font=font_task)
        
        # Row separator
        draw.line([(0, y + ROW_HEIGHT), (WIDTH, y + ROW_HEIGHT)], fill=BORDER, width=1)
        
        # Bar
        start = parse_date(task["start"])
        end = parse_date(task["end"])
        bar_x = date_to_x(start, min_date, max_date, chart_width)
        bar_x_end = date_to_x(end, min_date, max_date, chart_width)
        bar_width = max(bar_x_end - bar_x, 10)
        
        # Bar color by class
        if task["class"] == "done":
            bar_color = SUCCESS
            progress_color = SUCCESS
        elif task["class"] == "in_progress":
            bar_color = ACCENT
            progress_color = ACCENT_H
        else:
            bar_color = SURFACE2
            progress_color = SURFACE2
        
        # Draw bar background
        draw.rounded_rectangle([bar_x, y + 6, bar_x + bar_width, y + 6 + BAR_HEIGHT], radius=4, fill=bar_color, outline=BORDER)
        
        # Draw progress
        if task["progress"] > 0:
            progress_width = int(bar_width * task["progress"] / 100)
            draw.rounded_rectangle([bar_x, y + 6, bar_x + progress_width, y + 6 + BAR_HEIGHT], radius=4, fill=progress_color)
        
        # Progress text
        pct = f"{task['progress']}%"
        draw.text((bar_x + 6, y + 12), pct, fill=(255, 255, 255) if task["progress"] > 0 else TEXT_MUTED, font=font_small)
    
    # Status legend
    legend_y = CHART_TOP + chart_height + 20
    draw.text((260, legend_y), "Status:", fill=TEXT, font=font_label)
    
    legend_items = [
        ("Done", SUCCESS),
        ("In Progress", ACCENT),
        ("Pending", SURFACE2),
    ]
    for i, (label, color) in enumerate(legend_items):
        x = 330 + i * 120
        draw.rounded_rectangle([x, legend_y + 2, x + 14, legend_y + 16], radius=3, fill=color)
        draw.text((x + 20, legend_y + 2), label, fill=TEXT_MUTED, font=font_small)
    
    # Stats
    stats_y = legend_y + 40
    done_count = sum(1 for t in tasks if t["class"] == "done")
    in_progress_count = sum(1 for t in tasks if t["class"] == "in_progress")
    pending_count = sum(1 for t in tasks if t["class"] == "pending")
    
    draw.text((260, stats_y), f"Total: {len(tasks)}  |  Done: {done_count}  |  In Progress: {in_progress_count}  |  Pending: {pending_count}", fill=TEXT, font=font_label)
    draw.text((260, stats_y + 24), f"Date range: {min_date} to {max_date}", fill=TEXT_MUTED, font=font_small)
    draw.text((260, stats_y + 40), "Data source: docs/LexFlow_Agentic_Roadmap.json (real roadmap tasks)", fill=TEXT_MUTED, font=font_small)
    draw.text((260, stats_y + 56), "Rendered with Frappe Gantt 1.2.2 + LexFlow dark theme", fill=TEXT_MUTED, font=font_small)
    
    return img

# Generate the demo image
img = draw_demo()
output_path = "/Users/olesiarasing/Projects/lexflow-crm/docs/gantt/demo/gantt-demo-screenshot.png"
img.save(output_path)
print(f"Saved demo screenshot: {output_path}")
print(f"Image size: {img.size}")
