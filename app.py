import os
import uuid
from datetime import datetime
from io import BytesIO

from flask import Flask, request, jsonify, g, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl
import psycopg2
import psycopg2.extras

# ---------------- Setup ----------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:[#0meWork@897]@db.xtmgrvoyoniqejycagry.supabase.co:5432/postgres"
)

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})


# ---------------- Database ----------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = psycopg2.connect(DATABASE_URL, sslmode="require")
    return db


def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
          id SERIAL PRIMARY KEY,
          username TEXT UNIQUE,
          password_hash TEXT,
          token TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bp_readings (
          id SERIAL PRIMARY KEY,
          user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
          systolic INTEGER,
          diastolic INTEGER,
          created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    db.commit()
    cur.close()


@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


# ---------------- Auth Helper ----------------
def authenticate_request():
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE token=%s", (token,))
    user = cur.fetchone()
    cur.close()
    return user


# ---------------- Auth APIs ----------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    db = get_db()
    cur = db.cursor()
    try:
        pw_hash = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, pw_hash),
        )
        db.commit()
        return jsonify({"ok": True}), 201
    except psycopg2.Error:
        db.rollback()
        return jsonify({"error": "username taken"}), 400
    finally:
        cur.close()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        cur.close()
        return jsonify({"error": "invalid credentials"}), 401

    token = str(uuid.uuid4())
    cur.execute("UPDATE users SET token=%s WHERE id=%s", (token, user["id"]))
    db.commit()
    cur.close()

    return jsonify({"token": token, "username": user["username"]})


# ---------------- BP APIs ----------------
@app.route("/api/bp", methods=["POST"])
def submit_bp():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    try:
        sys = int(data.get("systolic"))
        dia = int(data.get("diastolic"))
    except Exception:
        return jsonify({"error": "systolic and diastolic must be integers"}), 400

    now = datetime.utcnow()
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO bp_readings (user_id, systolic, diastolic, created_at) VALUES (%s, %s, %s, %s)",
        (user["id"], sys, dia, now),
    )
    db.commit()
    cur.close()
    return jsonify({"ok": True})


@app.route("/api/bp/<int:bp_id>", methods=["PUT"])
def update_bp(bp_id):
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json() or {}
    try:
        sys = int(data.get("systolic"))
        dia = int(data.get("diastolic"))
    except Exception:
        return jsonify({"error": "systolic and diastolic must be integers"}), 400

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM bp_readings WHERE id=%s AND user_id=%s", (bp_id, user["id"]))
    if cur.fetchone() is None:
        cur.close()
        return jsonify({"error": "not found"}), 404

    cur.execute(
        "UPDATE bp_readings SET systolic=%s, diastolic=%s WHERE id=%s",
        (sys, dia, bp_id),
    )
    db.commit()
    cur.close()
    return jsonify({"ok": True})


@app.route("/api/bp/<int:bp_id>", methods=["DELETE"])
def delete_bp(bp_id):
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM bp_readings WHERE id=%s AND user_id=%s", (bp_id, user["id"]))
    if cur.fetchone() is None:
        cur.close()
        return jsonify({"error": "not found"}), 404

    cur.execute("DELETE FROM bp_readings WHERE id=%s", (bp_id,))
    db.commit()
    cur.close()
    return jsonify({"ok": True})


@app.route("/api/history", methods=["GET"])
def history():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT id, systolic, diastolic, created_at FROM bp_readings WHERE user_id=%s ORDER BY id DESC",
        (user["id"],),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return jsonify({"history": rows})


# ---------------- Excel Export ----------------
@app.route("/api/export", methods=["GET"])
def export_excel():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    start_date = request.args.get("start")
    end_date = request.args.get("end")

    query = "SELECT systolic, diastolic, created_at FROM bp_readings WHERE user_id=%s"
    params = [user["id"]]

    if start_date and end_date:
        query += " AND created_at BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BP Readings"
    ws.append(["Systolic", "Diastolic", "Date/Time"])

    for row in rows:
        ws.append([row["systolic"], row["diastolic"], row["created_at"].isoformat()])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"bp_readings_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ---------------- Health Check ----------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ---------------- Main ----------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
