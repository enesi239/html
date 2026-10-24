from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.security import check_password_hash
import sqlite3
import os
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv( override=True)

print("Username loaded:", os.environ.get("ADMIN_USERNAME"))
print("Password hash loaded:", bool(os.environ.get("ADMIN_PASSWORD_HASH")))
print("Secret key loaded:", os.environ.get("SECRET_KEY"))
print("Hash starts correctly:", os.environ.get("ADMIN_PASSWORD_HASH","").startswith("pbkdf2:sha256:"))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-before-deployment")
@app.before_request
def require_login():
    if request.endpoint in ("login" , "static"):
        return
    if not session.get("logged_in"):
        return redirect(url_for("login"))

DATABASE = "helpdesk.db" 


# Connect to the database
def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    try:
        connection.execute("ALTER TABLE tickets ADD COLUMN technician TEXT DEFAULT 'Unassigned'")
        connection.commit()
    except sqlite3.OperationalError:
        pass

    connection.row_factory = sqlite3.Row
    return connection


# Create the database table
def create_table():
    connection = get_db_connection()

    connection.execute ("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            staff_name TEXT NOT NULL,
            department TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            assigned_to TEXT DEFAULT 'Unassigned',
            technician TEXT DEFAULT 'Unassigned'
            )
        """)
    connection = get_db_connection()

    columns = connection.execute("PRAGMA table_info(tickets)").fetchall()
    column_names = [column["name"] for column in columns]

    if "assigned_to" not in column_names:
        connection.execute("""
            ALTER TABLE tickets ADD COLUMN assigned_to TEXT DEFAULT 'unassigned'
        """)

    connection.commit()
    connection.close()
#about
# Login page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        
        password = request.form.get("password", "")

        saved_username = os.environ.get("ADMIN_USERNAME", "admin")
        #saved_hash = os.environ.get("ADMIN_PASSWORD_HASH", " ")
        saved_password = os.environ.get("ADMIN_PASSWORD", " ")

        if username == saved_username and password == saved_password:
            session["logged_in"] = True
        return redirect(url_for("home"))

    flash("Invalid username or password.")

    return render_template("login.html")

# Log out
@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/about")
def about():
    return render_template("about.html")
# Dashboard
@app.route("/")
def home():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")

    connection = get_db_connection()

    query = "SELECT * FROM tickets WHERE 1=1"
    parameters = []

    # Search by staff name or issue title
    if search:
        query += """
            AND (
                staff_name LIKE ?
                OR title LIKE ?
            )
        """
        parameters.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    # Filter by status
    if status in ["Open", "In Progress", "Resolved"]:
        query += " AND status = ?"
        parameters.append(status)

    # Filter by priority
    if priority in ["Low", "Medium", "High"]:
        query += " AND priority = ?"
        parameters.append(priority)

    query += " ORDER BY id DESC"

    tickets = connection.execute(
        query, parameters
    ).fetchall()

    # Dashboard statistics: count all tickets
    total_tickets = connection.execute(
        "SELECT COUNT(*) FROM tickets"
    ).fetchone()[0]

    open_tickets = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Open'"
    ).fetchone()[0]

    progress_tickets = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'In Progress'"
    ).fetchone()[0]

    resolved_tickets = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'"
    ).fetchone()[0]

    high_priority = connection.execute(
        "SELECT COUNT(*) FROM tickets WHERE priority = 'High'"
    ).fetchone()[0]

    connection.close()

    return render_template(
        "index.html",
        tickets=tickets,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        progress_tickets=progress_tickets,
        resolved_tickets=resolved_tickets,
        search=search,
        selected_status=status,
        selected_priority=priority,
        high_priority=high_priority
    )
@app.route("/update-status/<int:ticket_id>", methods=["POST"])
def update_status(ticket_id):

    new_status = request.form.get("status")

    allowed_statuses = ["Open", "In Progress", "Resolved"]

    if new_status not in allowed_statuses:
        return "Invalid status", 400

    connection = get_db_connection()

    connection.execute(
        "UPDATE tickets SET status = ? WHERE id = ?",
        (new_status, ticket_id)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("home"))

@app.route("/ticket/<int:ticket_id>")
def ticket_details(ticket_id):
    connection = get_db_connection()

    ticket = connection.execute(
        "SELECT * FROM tickets WHERE id = ?",
        (ticket_id,)
    ).fetchone()

    connection.close()

    if ticket is None:
        return "Ticket not found", 404

    return render_template(
        "ticket_details.html",
        ticket=ticket
    )

# Create a ticket
@app.route("/create-ticket", methods=["GET", "POST"])
def create_ticket():

    if request.method == "POST":

        staff_name = request.form.get("staff_name")
        department = request.form.get("department")
        title = request.form.get("title")
        category = request.form.get("category")
        priority = request.form.get("priority")
        technician = request.form.get("technician")
        description = request.form.get("description")

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO tickets (
                staff_name,
                department,
                title,
                category,
                priority,
                description,
                technician
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            staff_name,
            department,
            title,
            category,
            priority,
            description,
            technician
        ))

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    return render_template("create_ticket.html")
@app.route("/assign-ticket/<int:ticket_id>", methods=["POST"])
def assign_ticket(ticket_id):

    technician = request.form.get("assigned_to", "").strip()

    allowed_technicians = [
        "Unassigned",
        "Ahmed",
        "Musa",
        "Abdullahi"
    ]

    if technician not in allowed_technicians:
        return "Invalid technician", 400

    connection = get_db_connection()

    connection.execute(
        "UPDATE tickets SET assigned_to = ? WHERE id = ?",
        (technician, ticket_id)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("home"))

@app.route("/delete-ticket/<int:ticket_id>", methods=["POST"])
def delete_ticket(ticket_id):
    connection = get_db_connection()

    connection.execute(
        "DELETE FROM tickets WHERE id = ?",
        (ticket_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("home"))
@app.route('/update_technician/<int:ticket_id>', methods=['POST'])
def update_technician(ticket_id):
    technician = request.form.get('technician')

    connection = get_db_connection()
    connection.row_factory = sqlite3.Row

    connection.execute(
        "UPDATE tickets SET technician = ? WHERE id = ?",
        (technician, ticket_id)
    )

    connection.commit()
    connection.close()

    return redirect(url_for('ticket_details', ticket_id=ticket_id))



if __name__ == "__main__":
    create_table()
    app.run(debug=True)