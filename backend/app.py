"""
Emergency Alert & Response System
Backend: Python (Flask) + SQLite (swap for MySQL by editing get_db())
Frontend: HTML / CSS / JS (served from frontend/templates and frontend/static)

Run locally:
    pip install -r requirements.txt
    python run.py
Then open http://127.0.0.1:5000

Deploy on Apache:
    See README.md -> "Deploying with Apache" section (mod_wsgi instructions)
"""

import os
import re
import sqlite3
import tempfile
from functools import wraps
from typing import List

from flask import (
    Flask, request, jsonify, session,
    render_template, redirect, url_for, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from backend.email_service import notify_alert_by_email

try:
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client as TwilioClient
except ImportError:  # Lets the app still start before optional SMS dependency is installed.
    TwilioClient = None
    TwilioRestException = Exception

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
DB_PATH = os.path.join(PROJECT_ROOT, "database", "emergency.db")
if os.environ.get("VERCEL"):
    # Vercel functions cannot persist writes inside the deployed project. This
    # keeps the demo functional between warm invocations; use DATABASE_PATH
    # with a managed database in production for durable alert records.
    DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "emergency.db"))
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "database", "schema.sql")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_ROOT, "frontend", "templates"),
    static_folder=PUBLIC_DIR,
    static_url_path="/static",
)
# Set SECRET_KEY in the environment before deploying. The fallback keeps the
# college-demo project usable locally, but must not be used in production.
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "development-only-change-this-secret-key"
)


# ---------------------------------------------------------------------------
# SMS delivery (Twilio)
# ---------------------------------------------------------------------------

def configured_alert_recipients() -> List[str]:
    """Return the comma-separated emergency numbers configured in the environment."""
    return [number.strip() for number in os.environ.get("ALERT_RECIPIENT_NUMBERS", "").split(",") if number.strip()]


def send_sms(to_number, body):
    """Send one SMS through Twilio without exposing credentials to the browser."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")
    if not all((account_sid, auth_token, from_number)):
        return False, "SMS is not configured on the server."
    if TwilioClient is None:
        return False, "The Twilio package is not installed on the server."

    try:
        TwilioClient(account_sid, auth_token).messages.create(
            body=body[:1600], from_=from_number, to=to_number
        )
        return True, None
    except TwilioRestException as exc:
        app.logger.error("Twilio could not send SMS to %s: %s", to_number, exc)
        return False, "SMS provider rejected the message."
    except Exception:
        app.logger.exception("Unexpected SMS delivery failure for %s", to_number)
        return False, "SMS delivery failed."


def location_link(lat, lng):
    if lat is None or lng is None:
        return "Location: not available"
    return f"Location: https://maps.google.com/?q={lat},{lng}"


def parse_coordinates(latitude, longitude):
    """Validate and normalize a latitude/longitude pair from a JSON request."""
    if latitude is None or longitude is None:
        return None, None, "Latitude and longitude are required"
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return None, None, "Invalid location coordinates"
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None, None, "Location coordinates are out of range"
    return latitude, longitude, None


def notify_emergency_contacts(alert_type, message, lat, lng, reporter_name):
    """Alert every configured response number; one failure does not stop the others."""
    recipients = configured_alert_recipients()
    if not recipients:
        return 0, ["No emergency mobile numbers are configured."]
    body = (
        f"EMERGENCY ALERT: {alert_type}\n"
        f"From: {reporter_name}\n"
        f"Message: {message or 'No additional details'}\n"
        f"{location_link(lat, lng)}"
    )
    delivered = 0
    errors = []
    for number in recipients:
        sent, error = send_sms(number, body)
        if sent:
            delivered += 1
        elif error:
            errors.append(error)
    return delivered, list(dict.fromkeys(errors))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """Get (or create) a per-request SQLite connection."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the database tables and seed the demo admin on first run."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    first_run = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    if first_run:
        seed_admin(conn)
    conn.close()


def seed_admin(conn):
    """Create a default admin account: username=admin / password=admin123"""
    existing = conn.execute(
        "SELECT 1 FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, phone, role) "
            "VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "System Admin", "0000000000", "admin"),
        )
        conn.commit()
        print("Seeded default admin -> username: admin | password: admin123")


# ---------------------------------------------------------------------------
# Auth helpers / decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        if session.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return wrapper


def citizen_required(f):
    """Restrict citizen-only alert actions to citizen accounts."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        if session.get("role") != "citizen":
            return jsonify({"error": "Citizen access required"}), 403
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Page routes (serve HTML)
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard_page"))
        return redirect(url_for("dashboard_page"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/dashboard")
def dashboard_page():
    if "user_id" not in session or session.get("role") != "citizen":
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", full_name=session.get("full_name"))


@app.route("/admin")
def admin_dashboard_page():
    if session.get("role") != "admin":
        return redirect(url_for("login_page"))
    return render_template("admin_dashboard.html", full_name=session.get("full_name"))


# ---------------------------------------------------------------------------
# Auth API
# ---------------------------------------------------------------------------

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required"}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not username or not password or not full_name:
        return jsonify({"error": "username, password and full_name are required"}), 400
    if len(username) > 50 or len(full_name) > 100 or len(phone) > 15:
        return jsonify({"error": "One or more fields are too long"}), 400
    if phone and not re.fullmatch(r"\+[1-9]\d{7,14}", phone):
        return jsonify({"error": "Phone number must use international format, e.g. +919876543210"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, password_hash, full_name, phone, role) "
            "VALUES (?, ?, ?, ?, 'citizen')",
            (username, generate_password_hash(password), full_name, phone),
        )
        db.commit()
        return jsonify({"message": "Registered successfully. Please log in."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username already exists"}), 400


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required"}), 400
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()

    if user and check_password_hash(user["password_hash"], password):
        session["user_id"] = user["user_id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        redirect_to = "/admin" if user["role"] == "admin" else "/dashboard"
        return jsonify({"message": "Login successful", "role": user["role"], "redirect": redirect_to})

    return jsonify({"error": "Invalid username or password"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ---------------------------------------------------------------------------
# Alert API
# ---------------------------------------------------------------------------

@app.route("/api/location", methods=["POST"])
@citizen_required
def api_location():
    """Store a citizen's current GPS location and notify configured responders."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required"}), 400

    # Accept the conventional frontend names and the existing alert names.
    latitude = data.get("latitude", data.get("lat"))
    longitude = data.get("longitude", data.get("lng"))
    latitude, longitude, error = parse_coordinates(latitude, longitude)
    if error:
        return jsonify({"error": error}), 400

    db = get_db()
    cursor = db.execute(
        "INSERT INTO location_shares (user_id, latitude, longitude) VALUES (?, ?, ?)",
        (session["user_id"], latitude, longitude),
    )
    db.commit()
    share_id = cursor.lastrowid

    reporter = db.execute(
        "SELECT full_name, phone, username FROM users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    reporter_name = reporter["full_name"] if reporter else "Unknown citizen"
    delivered, sms_errors = notify_emergency_contacts(
        "Location share", "Citizen shared their current location.", latitude, longitude, reporter_name
    )
    maps_link = f"https://www.google.com/maps?q={latitude},{longitude}"
    email_delivered, email_errors = notify_alert_by_email(
        "Other", "Citizen shared their current location.", reporter_name, maps_link,
        alert_id=f"loc-{share_id}",
        reporter_phone=reporter["phone"] if reporter else None,
        reporter_username=reporter["username"] if reporter else None,
        latitude=latitude, longitude=longitude,
    )
    return jsonify({
        "success": True,
        "message": "Location received and saved.",
        "maps_link": maps_link,
        "sms_delivered": delivered,
        "sms_errors": sms_errors,
        "email_delivered": email_delivered,
        "email_errors": email_errors,
    }), 201

@app.route("/api/send-alert", methods=["POST"])
@citizen_required

def api_send_alert():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON request body is required"}), 400
    alert_type = data.get("alert_type")
    message = (data.get("message") or "").strip()
    lat = data.get("lat")
    lng = data.get("lng")

    valid_types = ("Medical", "Fire", "Police", "Accident", "Other")
    if alert_type not in valid_types:
        return jsonify({"error": "Invalid alert type"}), 400
    if len(message) > 2_000:
        return jsonify({"error": "Message must be 2,000 characters or fewer"}), 400

    # A location is optional, but when supplied it must be a real coordinate.
    if (lat is None) != (lng is None):
        return jsonify({"error": "Latitude and longitude must be supplied together"}), 400
    if lat is not None:
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid location coordinates"}), 400
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            return jsonify({"error": "Location coordinates are out of range"}), 400

    db = get_db()
    cursor = db.execute(
        "INSERT INTO emergency_alerts (user_id, alert_type, message, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?)",
        (session["user_id"], alert_type, message, lat, lng),
    )
    db.commit()
    alert_id = cursor.lastrowid
    reporter = db.execute(
        "SELECT full_name, phone, username FROM users WHERE user_id = ?", (session["user_id"],)
    ).fetchone()
    reporter_name = reporter["full_name"] if reporter else "Unknown citizen"
    delivered, sms_errors = notify_emergency_contacts(alert_type, message, lat, lng, reporter_name)
    email_delivered, email_errors = notify_alert_by_email(
        alert_type, message, reporter_name,
        location_link(lat, lng).replace("Location: ", ""),
        alert_id=alert_id,
        reporter_phone=reporter["phone"] if reporter else None,
        reporter_username=reporter["username"] if reporter else None,
        latitude=lat, longitude=lng,
    )
    delivery_messages = []
    if email_delivered:
        delivery_messages.append(f"Email delivered to {email_delivered} response inbox(es).")
    if delivered:
        delivery_messages.append(f"SMS delivered to {delivered} emergency contact(s).")
    if not delivery_messages:
        delivery_messages.append("Alert saved, but no notification channel was delivered. Check the server configuration.")
    elif sms_errors:
        # Email may have notified responders successfully, so do not present a
        # successful alert as a failure just because the optional SMS channel
        # is unavailable.
        delivery_messages.append("SMS could not be delivered.")
    return jsonify({
        "message": "Emergency alert sent! Help is on the way. " + " ".join(delivery_messages),
        "sms_delivered": delivered,
        "sms_errors": sms_errors,
        "email_delivered": email_delivered,
        "email_errors": email_errors,
    }), 201


@app.route("/api/my-alerts", methods=["GET"])
@citizen_required
def api_my_alerts():
    db = get_db()
    rows = db.execute(
        "SELECT alert_id, alert_type, message, status, latitude, longitude, created_at "
        "FROM emergency_alerts WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/all-alerts", methods=["GET"])
@admin_required
def api_all_alerts():
    db = get_db()
    rows = db.execute(
        """
        SELECT a.alert_id, a.alert_type, a.message, a.status, a.latitude, a.longitude,
               a.created_at, u.full_name, u.phone, u.username
        FROM emergency_alerts a
        JOIN users u ON u.user_id = a.user_id
        ORDER BY
            CASE a.status WHEN 'Pending' THEN 0 WHEN 'Acknowledged' THEN 1 ELSE 2 END,
            a.created_at DESC
        """
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/update-status", methods=["POST"])
@admin_required


def api_update_status():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        
        return jsonify({"error": "A JSON request body is required"}), 400
    alert_id = data.get("alert_id")
    new_status = data.get("status")
    action_taken = (data.get("action_taken") or "").strip()

    if new_status not in ("Pending", "Acknowledged", "Resolved"):
        return jsonify({"error": "Invalid status"}), 400
    try:
        alert_id = int(alert_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid alert ID"}), 400
    if alert_id < 1:
        return jsonify({"error": "Invalid alert ID"}), 400
    if len(action_taken) > 255:
        return jsonify({"error": "Action taken must be 255 characters or fewer"}), 400

    db = get_db()
    alert = db.execute(
        """
        SELECT a.alert_type, u.phone, u.full_name
        FROM emergency_alerts a JOIN users u ON u.user_id = a.user_id
        WHERE a.alert_id = ?
        """, (alert_id,)
    ).fetchone()
    if not alert:
        return jsonify({"error": "Alert not found"}), 404
    db.execute(
        "UPDATE emergency_alerts SET status = ? WHERE alert_id = ?",
        (new_status, alert_id),
    )
    db.execute(
        "INSERT INTO responders (alert_id, admin_id, action_taken) VALUES (?, ?, ?)",
        (alert_id, session["user_id"], action_taken or f"Status changed to {new_status}"),
    )
    db.commit()
    sms_delivered = False
    if alert["phone"]:
        sms_delivered, _ = send_sms(
            alert["phone"],
            f"Emergency Alert Update: Your {alert['alert_type']} alert is now {new_status}. "
            f"{action_taken or ''}".strip(),
        )
    return jsonify({"message": "Status updated", "sms_delivered": sms_delivered})


@app.route("/api/stats", methods=["GET"])
@admin_required
def api_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM emergency_alerts").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) c FROM emergency_alerts WHERE status='Pending'").fetchone()["c"]
    resolved = db.execute("SELECT COUNT(*) c FROM emergency_alerts WHERE status='Resolved'").fetchone()["c"]
    by_type = db.execute(
        "SELECT alert_type, COUNT(*) c FROM emergency_alerts GROUP BY alert_type"
    ).fetchall()
    return jsonify({
        "total": total,
        "pending": pending,
        "resolved": resolved,
        "by_type": {r["alert_type"]: r["c"] for r in by_type},
    })


# ---------------------------------------------------------------------------
# Initialise on import as well as when running directly. This is essential for
# Flask's test client and for deployments through mod_wsgi/Gunicorn.
with app.app_context():
    init_db()


# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
