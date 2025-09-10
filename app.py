import os
import uuid
from datetime import datetime
from io import BytesIO

from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import openpyxl

# ---------------- Setup ----------------
app = Flask(__name__)
# Allow CORS for all routes, including root and /health
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# ---------------- Database Config (Clever Cloud MySQL) ----------------
DB_HOST = os.getenv("MYSQL_ADDON_HOST", "bxlgjcwgxetaghluuycc-mysql.services.clever-cloud.com")
DB_PORT = os.getenv("MYSQL_ADDON_PORT", "3306")
DB_NAME = os.getenv("MYSQL_ADDON_DB", "bxlgjcwgxetaghluuycc")
DB_USER = os.getenv("MYSQL_ADDON_USER", "uyvxlru6qtyjaadu")
DB_PASS = os.getenv("MYSQL_ADDON_PASSWORD", "AVNxHAeU1C76JuCF5rYq")

app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------- Models ----------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    token = db.Column(db.String(255), nullable=True)


class BPReading(db.Model):
    __tablename__ = "bp_readings"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    systolic = db.Column(db.Integer, nullable=False)
    diastolic = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------- Auth Helper ----------------
def authenticate_request():
    auth = request.headers.get("Authorization", "")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    return User.query.filter_by(token=token).first()

# ---------------- Auth APIs ----------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username taken"}), 400

    pw_hash = generate_password_hash(password)
    new_user = User(username=username, password_hash=pw_hash)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"ok": True}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401

    token = str(uuid.uuid4())
    user.token = token
    db.session.commit()

    return jsonify({"token": token, "username": user.username})

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

    reading = BPReading(user_id=user.id, systolic=sys, diastolic=dia)
    db.session.add(reading)
    db.session.commit()
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

    reading = BPReading.query.filter_by(id=bp_id, user_id=user.id).first()
    if not reading:
        return jsonify({"error": "not found"}), 404

    reading.systolic = sys
    reading.diastolic = dia
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/bp/<int:bp_id>", methods=["DELETE"])
def delete_bp(bp_id):
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    reading = BPReading.query.filter_by(id=bp_id, user_id=user.id).first()
    if not reading:
        return jsonify({"error": "not found"}), 404

    db.session.delete(reading)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/history", methods=["GET"])
def history():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    readings = BPReading.query.filter_by(user_id=user.id).order_by(BPReading.id.desc()).all()
    rows = [
        {
            "id": r.id,
            "systolic": r.systolic,
            "diastolic": r.diastolic,
            "created_at": r.created_at.isoformat(),
        }
        for r in readings
    ]
    return jsonify({"history": rows})

# ---------------- Excel Export ----------------
@app.route("/api/export", methods=["GET"])
def export_excel():
    user = authenticate_request()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    start_date = request.args.get("start")
    end_date = request.args.get("end")

    query = BPReading.query.filter_by(user_id=user.id)

    if start_date and end_date:
        query = query.filter(BPReading.created_at.between(start_date, end_date))

    rows = query.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BP Readings"

    ws.append(["Systolic", "Diastolic", "Date/Time"])
    for r in rows:
        ws.append([r.systolic, r.diastolic, r.created_at.isoformat()])

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
@app.route("/api/health", methods=["GET"])
def api_health():
    return jsonify({"status": "ok", "message": "Flask app running on Render"})

# Add root and plain health routes
@app.route("/", methods=["GET"])
def root():
    return jsonify({"message": "Backend is running on Render"}), 200

@app.route("/health", methods=["GET"])
def plain_health():
    return jsonify({"status": "ok", "message": "Health check passed"}), 200

# ---------------- Main ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
