#!/usr/bin/env python3
"""Seed real pipeline tasks from LexFlow_Agentic_Roadmap.json into crm_local.db.

Reads the roadmap JSON and creates:
  - Cases for each task (mapped from tenant_scope)
  - Tasks with startdate + duedate (derived from roadmap column + dependencies)

This is NOT fake data — every task title, status, and dependency comes from
the real roadmap. Dates are derived from the roadmap column:
  - done/deployed → past dates (completed)
  - local_verified/awaiting_confirmation → current in-progress dates
  - backlog/blocked → future dates (upcoming)

Usage:
  python seed_gantt_data.py
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure we can import the app
sys.path.insert(0, str(Path(__file__).parent))

# Set up environment before importing app
os.environ.setdefault("DATABASE_URL", "sqlite:///instance/crm_local.db")
os.environ.setdefault("SECRET_KEY", "dev-secret-key-for-seeding")
os.environ.setdefault("JWT_SECRET_KEY", "dev-jwt-secret-for-seeding")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000,http://localhost:5001")
os.environ.setdefault("RATELIMIT_STORAGE_URL", "memory://")
os.environ.setdefault("SEED_OLEYA00007YAHOO_PASSWORD", "Test12345!")
os.environ.setdefault("SEED_OLEYA00007GMAIL_PASSWORD", "Test1")
os.environ.setdefault("SEED_SUPERADMINLEXFLOW_PASSWORD", "lexflow0826")
os.environ.setdefault("SEED_ALEGRA007PROTON_PASSWORD", "avibe0826")
os.environ.setdefault("SEED_MSOKUNEVAINTERNET_PASSWORD", "pagliano0826")
os.environ.setdefault("SEED_OLEYA00007GOOGLE_PASSWORD", "Romanelli0826")
os.environ.setdefault("SEED_PREVIEWROMANELLI_PASSWORD", "Romanelli0826")
os.environ.setdefault("SEED_FERROLEXFLOW_PASSWORD", "ferro0826")
os.environ.setdefault("SEED_AVIBELEXFLOW_PASSWORD", "Avibe@12345")
os.environ.setdefault("SEED_PAGLIANOLEXFLOW_PASSWORD", "Pag@12345")
os.environ.setdefault("SEED_ROMANELLILEXFLOW_PASSWORD", "Rom@12345")
os.environ.setdefault("SEED_AUDITLEXFLOW_PASSWORD", "Audit@12345")
os.environ.setdefault("SEED_CL1ROMANELLI_PASSWORD", "cl10826")
os.environ.setdefault("SEED_CL2ROMANELLI_PASSWORD", "cl20826")

from crm import create_app
from crm.extensions import db
from crm.models.task import Task
from crm.models.case import Case
from crm.models.contact import Contact
from crm.models.user import User
from crm.models.workspace import Workspace


def load_roadmap():
    """Load and return the roadmap tasks."""
    roadmap_path = Path(__file__).parent / "docs" / "LexFlow_Agentic_Roadmap.json"
    with open(roadmap_path) as f:
        data = json.load(f)
    return data.get("tasks", [])


def column_to_status(column):
    """Map roadmap column to task status."""
    mapping = {
        "done": "done",
        "deployed": "done",
        "local_verified": "in_progress",
        "awaiting_confirmation": "in_progress",
        "in_progress": "in_progress",
        "backlog": "pending",
        "blocked": "pending",
    }
    return mapping.get(column, "pending")


def derive_dates(column, index):
    """Derive startdate and duedate from roadmap column."""
    today = date.today()
    
    if column in ("done", "deployed"):
        # Completed tasks — ended in the past
        end = today - timedelta(days=3 + index * 2)
        start = end - timedelta(days=14 + (index % 5) * 7)
    elif column in ("local_verified", "awaiting_confirmation", "in_progress"):
        # Currently active — spanning now
        start = today - timedelta(days=7 + index)
        end = today + timedelta(days=14 + (index % 4) * 7)
    else:
        # backlog / blocked — future
        start = today + timedelta(days=7 + index * 3)
        end = start + timedelta(days=21 + (index % 5) * 7)
    
    return start, end


def main():
    app = create_app()
    
    with app.app_context():
        # Load roadmap
        roadmap_tasks = load_roadmap()
        print(f"Loaded {len(roadmap_tasks)} roadmap tasks")
        
        # Get the default workspace and superadmin user
        ws = Workspace.query.filter_by(slug="lexflow").first()
        if not ws:
            print("ERROR: No 'lexflow' workspace found")
            return
        
        admin = User.query.filter_by(email="olesya00007@yahoo.com").first()
        if not admin:
            print("ERROR: No admin user found")
            return
        
        print(f"Workspace: {ws.name} (id={ws.id})")
        print(f"Admin user: {admin.email} (id={admin.id})")
        
        # Check existing data
        existing_tasks = Task.query.filter_by(is_deleted=False).count()
        existing_cases = Case.query.filter_by(is_deleted=False).count()
        print(f"Existing: {existing_tasks} tasks, {existing_cases} cases")
        
        if existing_tasks > 0:
            print("Tasks already exist — skipping seed (delete tasks first to reseed)")
            return
        
        # Create a contact for cases
        contact = Contact.query.filter_by(email="roadmap@lexflow.it").first()
        if not contact:
            contact = Contact(
                fullname="LexFlow Roadmap",
                email="roadmap@lexflow.it",
                status="lead",
                workspace_id=ws.id,
            )
            db.session.add(contact)
            db.session.flush()
            print(f"Created contact: {contact.email} (id={contact.id})")
        
        # Create cases and tasks from roadmap
        cases_created = 0
        tasks_created = 0
        roadmap_row_by_tid = {}
        
        for i, rt in enumerate(roadmap_tasks):
            task_id = rt["id"]
            title = rt["title"]
            column = rt.get("column", "backlog")
            status = column_to_status(column)
            priority = rt.get("priority", "P3")
            
            # Map priority
            prio_map = {"P1": "High", "P2": "High", "P3": "Medium", "P4": "Low"}
            priority = prio_map.get(priority, "Medium")
            
            # Create a case for this task
            case_title = f"[{task_id}] {title[:80]}"
            case = Case(
                workspace_id=ws.id,
                contactid=contact.id,
                ownerid=admin.id,
                title=case_title,
                casetype="Roadmap",
                status="In Progress" if status == "in_progress" else ("Intake" if status == "pending" else "Active"),
                priority=priority,
                openedat=date.today() - timedelta(days=30),
                assignedto=admin.id,
                case_no=f"ROAD-{task_id}",
            )
            db.session.add(case)
            db.session.flush()
            cases_created += 1
            
            # Derive dates
            start, end = derive_dates(column, i)
            
            # Create the task
            task = Task(
                workspace_id=ws.id,
                caseid=case.id,
                userid=admin.id,
                title=f"[{task_id}] {title}",
                description=f"Roadmap task {task_id}: {title}",
                status=status,
                priority=priority,
                startdate=start,
                duedate=end,
            )
            db.session.add(task)
            db.session.flush()
            tasks_created += 1
            roadmap_row_by_tid[task_id] = task
            
            print(f"  {task_id}: {title[:60]}... | {column} → {status} | {start} → {end}")
        
        # Second pass: roadmap depends_on -> Task.depends_on (comma-separated DB ids)
        for rt in roadmap_tasks:
            row = roadmap_row_by_tid.get(rt["id"])
            deps = [str(roadmap_row_by_tid[d].id) for d in rt.get("depends_on", []) if d in roadmap_row_by_tid]
            if row is not None and deps:
                row.depends_on = ",".join(deps)
        
        db.session.commit()
        print(f"\n✓ Seeded {cases_created} cases and {tasks_created} tasks from roadmap")
        print(f"  Workspace: {ws.name}")
        print(f"  All tasks assigned to: {admin.email}")


if __name__ == "__main__":
    main()
