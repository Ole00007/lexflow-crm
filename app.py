from pathlib import Path
from datetime import datetime
import secrets
import sqlite3

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {"pdf", "doc", "docx", "png", "jpg", "jpeg", "txt"}

PRACTICES = [
    "Commercial",
    "Employment",
    "Real Estate",
    "Family",
    "Debt Collection",
    "Shipping / Logistics",
    "Other",
]
STATUSES = [
    "New intake",
    "Conflict check",
    "Lawyer review",
    "Waiting client docs",
    "Quoted",
    "Engaged",
    "Closed",
]

app = Flask(__name__)
app.config["SECRET_KEY"] = "lexflow-dev-secret-key"


def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def get_db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def ensure_matters_table(connection):
    expected_columns = [
        "id", "created_at", "token", "client_name", "email",
        "phone", "company", "practice_area", "urgency",
        "description", "status", "internal_notes",
    ]
    existing_columns = [
        row["name"]
        for row in connection.execute("PRAGMA table_info(matters)").fetchall()
    ]
    create_matters_sql = """
        CREATE TABLE IF NOT EXISTS matters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            client_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            practice_area TEXT NOT NULL,
            urgency TEXT DEFAULT 'Medium',
            description TEXT,
            status TEXT NOT NULL DEFAULT 'New intake',
            internal_notes TEXT DEFAULT ''
        );
    """
    if not existing_columns:
        connection.execute(create_matters_sql)
        return
    if existing_columns == expected_columns:
        return
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("""
        CREATE TABLE matters_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            token TEXT NOT NULL UNIQUE,
            client_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            company TEXT,
            practice_area TEXT NOT NULL,
            urgency TEXT DEFAULT 'Medium',
            description TEXT,
            status TEXT NOT NULL DEFAULT 'New intake',
            internal_notes TEXT DEFAULT ''
        );
    """)
    select_values = []
    for column in expected_columns:
        if column in existing_columns:
            select_values.append(column)
        elif column == "created_at":
            select_values.append("CURRENT_TIMESTAMP")
        elif column == "practice_area":
            select_values.append("'Other'")
        elif column == "urgency":
            select_values.append("'Medium'")
        elif column == "status":
            select_values.append("'New intake'")
        elif column == "internal_notes":
            select_values.append("''")
        else:
            select_values.append("NULL")
    connection.execute(
        f"""
        INSERT INTO matters_new ({", ".join(expected_columns)})
        SELECT {", ".join(select_values)}
        FROM matters;
        """
    )
    connection.execute("DROP TABLE matters")
    connection.execute("ALTER TABLE matters_new RENAME TO matters")
    connection.execute("PRAGMA foreign_keys = ON")


def init_db():
    DATA_DIR.mkdir(exist_ok=True)
    UPLOADS_DIR.mkdir(exist_ok=True)
    with get_db_connection() as connection:
        ensure_matters_table(connection)
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matter_id INTEGER NOT NULL,
                stored_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (matter_id) REFERENCES matters (id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matter_id INTEGER NOT NULL,
                event_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (matter_id) REFERENCES matters (id) ON DELETE CASCADE
            );
        """)


# Init DB on startup (works with Gunicorn on Railway)
with app.app_context():
    init_db()


@app.route("/")
def index():
    return render_template("index.html", practices=PRACTICES)


@app.route("/demo/seed")
def seed_demo():
    created = seed_demo_data()
    if created:
        flash("Demo matters created.")
    else:
        flash("Demo data already exists.")
    return redirect(url_for("admin"))


def seed_demo_data():
    with get_db_connection() as connection:
        existing_count = connection.execute("SELECT COUNT(*) FROM matters").fetchone()[0]
        if existing_count:
            return False
        demo_matters = [
            {
                "token": secrets.token_hex(8).upper(),
                "client_name": "Maria Rossi",
                "email": "maria.rossi@example.com",
                "phone": "+39 010 000 0001",
                "company": "Rossi Design SRL",
                "practice_area": "Commercial",
                "urgency": "High",
                "description": "Review of a supplier contract before signature.",
                "status": "Lawyer review",
                "events": [
                    ("New intake", "Matter created from intake form."),
                    ("Conflict check", "Conflict check completed."),
                    ("Lawyer review", "Your documents are being reviewed."),
                ],
            },
            {
                "token": secrets.token_hex(8).upper(),
                "client_name": "Luca Bianchi",
                "email": "luca.bianchi@example.com",
                "phone": "+39 010 000 0002",
                "company": "",
                "practice_area": "Employment",
                "urgency": "Medium",
                "description": "Review of employment termination documents.",
                "status": "Waiting client docs",
                "events": [
                    ("New intake", "Matter created from intake form."),
                    ("Waiting client docs", "Waiting for supporting documents."),
                ],
            },
            {
                "token": secrets.token_hex(8).upper(),
                "client_name": "Giulia Conti",
                "email": "giulia.conti@example.com",
                "phone": "",
                "company": "Conti Logistics",
                "practice_area": "Shipping / Logistics",
                "urgency": "Critical",
                "description": "Urgent review of a shipping dispute notice.",
                "status": "Quoted",
                "events": [
                    ("New intake", "Matter created from intake form."),
                    ("Lawyer review", "Initial request reviewed."),
                    ("Quoted", "A fee quote has been prepared."),
                ],
            },
        ]
        for demo in demo_matters:
            created_at = datetime.utcnow().isoformat()
            cursor = connection.execute(
                """
                INSERT INTO matters (
                    created_at, token, client_name, email, phone,
                    company, practice_area, urgency, description,
                    status, internal_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at, demo["token"], demo["client_name"],
                    demo["email"], demo["phone"], demo["company"],
                    demo["practice_area"], demo["urgency"],
                    demo["description"], demo["status"],
                    "Demo-only internal note.",
                ),
            )
            matter_id = cursor.lastrowid
            for status, note in demo["events"]:
                connection.execute(
                    "INSERT INTO events (matter_id, event_time, status, note) VALUES (?, ?, ?, ?)",
                    (matter_id, datetime.utcnow().isoformat(), status, note),
                )
        return True


@app.route("/submit", methods=["POST"])
def submit():
    client_name = request.form.get("client_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    company = request.form.get("company", "").strip()
    practice_area = request.form.get("practice_area", "").strip()
    urgency = request.form.get("urgency", "Medium").strip() or "Medium"
    description = request.form.get("description", "").strip()

    if not client_name or not email or not practice_area:
        flash("Required fields missing.")
        return redirect(url_for("index"))

    token = secrets.token_hex(8).upper()
    created_at = datetime.utcnow().isoformat()

    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO matters (
                created_at, token, client_name, email, phone,
                company, practice_area, urgency, description,
                status, internal_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (created_at, token, client_name, email, phone, company,
             practice_area, urgency, description, "New intake", ""),
        )
        matter_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO events (matter_id, event_time, status, note) VALUES (?, ?, ?, ?)",
            (matter_id, datetime.utcnow().isoformat(), "New intake", "Matter created from intake form."),
        )
        for uploaded in request.files.getlist("documents"):
            if not uploaded or not uploaded.filename:
                continue
            if not allowed_file(uploaded.filename):
                continue
            original_name = uploaded.filename
            safe_name = secure_filename(original_name)
            unique_name = f"{secrets.token_hex(8)}_{safe_name}"
            uploaded.save(UPLOAD_DIR / unique_name)
            connection.execute(
                """
                INSERT INTO documents (matter_id, stored_name, original_name, uploaded_at)
                VALUES (?, ?, ?, ?)
                """,
                (matter_id, unique_name, original_name, datetime.utcnow().isoformat()),
            )

    return redirect(url_for("status_page", token=token))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(str(UPLOAD_DIR), filename)


@app.route("/status/<token>")
def status_page(token):
    with get_db_connection() as connection:
        matter = connection.execute(
            "SELECT * FROM matters WHERE token = ?", (token,)
        ).fetchone()
        if matter is None:
            return "Matter not found. Please check your link.", 404
        docs = connection.execute(
            "SELECT * FROM documents WHERE matter_id = ? ORDER BY uploaded_at DESC",
            (matter["id"],),
        ).fetchall()
        events = connection.execute(
            "SELECT * FROM events WHERE matter_id = ? ORDER BY event_time DESC",
            (matter["id"],),
        ).fetchall()
    return render_template("status.html", matter=matter, docs=docs, events=events, statuses=STATUSES)


@app.route("/admin")
def admin():
    with get_db_connection() as connection:
        matters = connection.execute(
            "SELECT * FROM matters ORDER BY created_at DESC"
        ).fetchall()
    return render_template("admin.html", matters=matters, statuses=STATUSES)


@app.route("/admin/matter/<int:matter_id>", methods=["GET", "POST"])
def admin_matter(matter_id):
    with get_db_connection() as connection:
        matter = connection.execute(
            "SELECT * FROM matters WHERE id = ?", (matter_id,)
        ).fetchone()
        if matter is None:
            return "Matter not found.", 404

        if request.method == "POST":
            status = request.form.get("status", "").strip() or matter["status"]
            internal_notes = request.form.get("internal_notes", "").strip()
            event_note = request.form.get("event_note", "").strip()
            note = event_note or f"Status updated to {status}."
            connection.execute(
                "UPDATE matters SET status = ?, internal_notes = ? WHERE id = ?",
                (status, internal_notes, matter_id),
            )
            connection.execute(
                "INSERT INTO events (matter_id, event_time, status, note) VALUES (?, ?, ?, ?)",
                (matter_id, datetime.utcnow().isoformat(), status, note),
            )
            return redirect(url_for("admin_matter", matter_id=matter_id))

        docs = connection.execute(
            "SELECT * FROM documents WHERE matter_id = ? ORDER BY uploaded_at DESC",
            (matter_id,),
        ).fetchall()
        events = connection.execute(
            "SELECT * FROM events WHERE matter_id = ? ORDER BY event_time DESC",
            (matter_id,),
        ).fetchall()

    return render_template(
        "admin_matter.html", matter=matter, docs=docs, events=events, statuses=STATUSES
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
