
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "super_secret_key_for_demo"  # change in production

DB_NAME = "voting.db"


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Students table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usn TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            branch TEXT NOT NULL,
            has_voted INTEGER DEFAULT 0
        );
    """)

    # Candidates table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            branch TEXT NOT NULL,
            party TEXT NOT NULL,
            votes INTEGER DEFAULT 0
        );
    """)

    conn.commit()
    conn.close()


@app.before_first_request
def setup():
    init_db()


@app.route("/")
def home():
    return redirect(url_for("student_login"))


# ------------------ STUDENT AUTH ------------------ #

@app.route("/student_login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        usn = request.form.get("usn").strip()
        password = request.form.get("password").strip()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE usn = ? AND password = ?", (usn, password))
        student = cur.fetchone()
        conn.close()

        if student:
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]
            session["student_branch"] = student["branch"]
            session["student_has_voted"] = student["has_voted"]
            flash("Login successful!", "success")
            return redirect(url_for("vote"))
        else:
            flash("Invalid USN or password", "error")

    return render_template("student_login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usn = request.form.get("usn").strip()
        name = request.form.get("name").strip()
        password = request.form.get("password").strip()
        branch = request.form.get("branch").strip()

        if not usn or not name or not password or not branch:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO students (usn, name, password, branch) VALUES (?, ?, ?, ?)",
                (usn, name, password, branch),
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("student_login"))
        except sqlite3.IntegrityError:
            flash("USN already registered.", "error")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("student_login"))


# ------------------ STUDENT VOTING & RESULTS ------------------ #

def login_required_student(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if "student_id" not in session:
            flash("Please login as student.", "error")
            return redirect(url_for("student_login"))
        return f(*args, **kwargs)

    return wrapper


@app.route("/vote", methods=["GET", "POST"])
@login_required_student
def vote():
    conn = get_db_connection()
    cur = conn.cursor()

    student_branch = session.get("student_branch")
    student_id = session.get("student_id")

    cur.execute("SELECT has_voted FROM students WHERE id = ?", (student_id,))
    row = cur.fetchone()
    has_voted = row["has_voted"] if row else 0

    if request.method == "POST":
        if has_voted:
            flash("You have already voted.", "error")
        else:
            candidate_id = request.form.get("candidate")
            if candidate_id:
                cur.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
                cur.execute("UPDATE students SET has_voted = 1 WHERE id = ?", (student_id,))
                conn.commit()
                session["student_has_voted"] = 1
                flash("Your vote has been recorded successfully.", "success")
                has_voted = 1
            else:
                flash("Please select a candidate before submitting.", "error")

    cur.execute("SELECT * FROM candidates WHERE branch = ?", (student_branch,))
    candidates = cur.fetchall()
    conn.close()

    return render_template("vote.html", candidates=candidates, has_voted=has_voted, branch=student_branch)


@app.route("/results")
@login_required_student
def results():
    conn = get_db_connection()
    cur = conn.cursor()

    # Get all branches that have candidates
    cur.execute("SELECT DISTINCT branch FROM candidates ORDER BY branch;")
    branches = [row["branch"] for row in cur.fetchall()]

    branch_results = {}
    for branch in branches:
        cur.execute(
            "SELECT name, party, votes FROM candidates WHERE branch = ? ORDER BY votes DESC, name ASC;",
            (branch,),
        )
        branch_results[branch] = cur.fetchall()

    conn.close()
    return render_template("results.html", branch_results=branch_results)


# ------------------ ADMIN AUTH ------------------ #

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


def login_required_admin(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if "is_admin" not in session or not session["is_admin"]:
            flash("Please login as admin to access this page.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)

    return wrapper


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")


@app.route("/admin_logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "success")
    return redirect(url_for("admin_login"))


# ------------------ ADMIN PAGES ------------------ #

@app.route("/admin/dashboard")
@login_required_admin
def admin_dashboard():
    return render_template("admin_dashboard.html")


@app.route("/admin/add_candidate", methods=["GET", "POST"])
@login_required_admin
def add_candidate():
    if request.method == "POST":
        name = request.form.get("name").strip()
        branch = request.form.get("branch").strip()
        party = request.form.get("party").strip()

        if not name or not branch or not party:
            flash("All fields are required.", "error")
            return redirect(url_for("add_candidate"))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO candidates (name, branch, party) VALUES (?, ?, ?)",
            (name, branch, party),
        )
        conn.commit()
        conn.close()
        flash("Candidate added successfully.", "success")
        return redirect(url_for("add_candidate"))

    return render_template("add_candidate.html")


@app.route("/admin/manage_candidates")
@login_required_admin
def manage_candidates():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidates ORDER BY branch, name;")
    candidates = cur.fetchall()
    conn.close()
    return render_template("manage_candidates.html", candidates=candidates)


@app.route("/admin/edit_candidate/<int:candidate_id>", methods=["GET", "POST"])
@login_required_admin
def edit_candidate(candidate_id):
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name").strip()
        branch = request.form.get("branch").strip()
        party = request.form.get("party").strip()

        if not name or not branch or not party:
            flash("All fields are required.", "error")
            return redirect(url_for("edit_candidate", candidate_id=candidate_id))

        cur.execute(
            "UPDATE candidates SET name = ?, branch = ?, party = ? WHERE id = ?",
            (name, branch, party, candidate_id),
        )
        conn.commit()
        conn.close()
        flash("Candidate updated successfully.", "success")
        return redirect(url_for("manage_candidates"))

    cur.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    candidate = cur.fetchone()
    conn.close()

    if not candidate:
        flash("Candidate not found.", "error")
        return redirect(url_for("manage_candidates"))

    return render_template("edit_candidate.html", candidate=candidate)


@app.route("/admin/delete_candidate/<int:candidate_id>", methods=["POST"])
@login_required_admin
def delete_candidate(candidate_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    conn.commit()
    conn.close()
    flash("Candidate deleted successfully.", "success")
    return redirect(url_for("manage_candidates"))


@app.route("/admin/reset_votes", methods=["POST"])
@login_required_admin
def reset_votes():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE candidates SET votes = 0;")
    cur.execute("UPDATE students SET has_voted = 0;")
    conn.commit()
    conn.close()
    flash("All votes have been reset.", "success")
    return redirect(url_for("manage_candidates"))


@app.route("/admin/final_results")
@login_required_admin
def admin_final_results():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT branch FROM candidates ORDER BY branch;")
    branches = [row["branch"] for row in cur.fetchall()]

    branch_results = {}
    for branch in branches:
        cur.execute(
            "SELECT name, party, votes FROM candidates WHERE branch = ? ORDER BY votes DESC, name ASC;",
            (branch,),
        )
        branch_results[branch] = cur.fetchall()

    conn.close()
    return render_template("admin_results.html", branch_results=branch_results)


if __name__ == "__main__":
    # Run in debug for development
    app.run(debug=True)
