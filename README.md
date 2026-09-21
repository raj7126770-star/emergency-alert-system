# Emergency Alert & Response System

A major project for B.Tech CSE — a web app where citizens can send emergency
alerts (Medical / Fire / Police / Accident / Other) with their live location,
and admins/responders monitor and resolve them from a live dashboard.

**Stack:** HTML, CSS, JavaScript (frontend) · Python/Flask (backend) ·
SQLite/MySQL (database) · Apache (hosting) · Session-based username/password
authentication.

---

## 1. Features

- User registration & login (passwords hashed with Werkzeug, never stored in plain text)
- Two roles: **Citizen** (send alerts) and **Admin** (manage alerts)
- Emergency alert form with type selection + auto-captured GPS location (`navigator.geolocation`)
- Authenticated location-sharing API that stores coordinates, returns a Google Maps link,
  and notifies configured emergency contacts by SMS
- Citizen dashboard: view your own alert history and live status
- Admin dashboard: live-updating list of all alerts (polls every 10s), filter by status,
  acknowledge/resolve alerts, quick stats (total / pending / resolved)
- Clicking an alert's location opens it directly in Google Maps
- Clean, responsive UI — no frameworks, pure HTML/CSS/JS

---

## 2. Project Structure

```
emergency-alert-system/
├── app.py                  # Flask app: routes, API, auth, DB logic
├── requirements.txt
├── database/
│   ├── schema.sql           # Table definitions
│   └── emergency.db         # Created automatically on first run
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html       # Citizen view
│   └── admin_dashboard.html # Admin view
└── static/
    ├── css/style.css
    └── js/
        ├── auth.js           # login/register/logout
        ├── alerts.js         # citizen: send + view own alerts
        └── admin.js          # admin: monitor + update all alerts
```

---

## 3. Running Locally (development)

The current layout is documented in `STRUCTURE.md`: Flask code is in `backend/`,
browser templates are in `frontend/`, public browser assets are in `public/`,
and persistent data is in `database/`.

```bash
cd emergency-alert-system
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**

A default admin account is created automatically on first run:

| Username | Password |
|---|---|
| `admin` | `admin123` |

**Change this password (or remove the seed_admin call) before any real deployment.**

Register a normal account from `/register` to test the citizen flow.

---

## 4. Switching from SQLite to MySQL

The project ships with SQLite so it runs with zero external setup — ideal for
a college demo. To use MySQL instead (recommended if your report specifically
requires "SQL" as a separate server):

1. `pip install mysql-connector-python`
2. Run `database/schema.sql` against MySQL (minor syntax tweaks needed —
   replace `AUTOINCREMENT` with `AUTO_INCREMENT`, and `CHECK(...)` columns with
   real `ENUM(...)` types as shown in the commented example at the top of the
   project plan).
3. Replace the `get_db()` function in `backend/app.py` with a `mysql.connector.connect(...)`
   call using your host/user/password/database, and swap `?` placeholders for `%s`.

Everything else (routes, JS, HTML) stays the same since the SQL logic is
isolated inside `get_db()` and the query functions.

---

## 5. Deploying with Apache

Apache doesn't execute Python natively, so pick one of these two approaches:

### Option A — `mod_wsgi` (classic, good for a viva/demo)

1. `pip install mod_wsgi`
2. Create `emergency.wsgi`:
   ```python
   import sys
   sys.path.insert(0, '/path/to/emergency-alert-system')
   from backend.app import app as application
   ```
3. Add to your Apache config:
   ```apache
   WSGIScriptAlias / /path/to/emergency-alert-system/emergency.wsgi
   <Directory /path/to/emergency-alert-system>
       Require all granted
   </Directory>
   Alias /static /path/to/emergency-alert-system/frontend/static
   ```
4. Restart Apache.

### Option B — Apache as a reverse proxy (closer to production practice)

1. Run the app with a production server: `pip install gunicorn` then
   `gunicorn -w 4 -b 127.0.0.1:8000 backend.app:app`
2. Enable Apache's proxy modules: `a2enmod proxy proxy_http`
3. In your Apache vhost config:
   ```apache
   ProxyPass / http://127.0.0.1:8000/
   ProxyPassReverse / http://127.0.0.1:8000/
   ```
4. Restart Apache. Gunicorn keeps running in the background (e.g. via `systemd`).

Mention both in your project report — Option A is simpler to explain, Option B
shows awareness of how Python apps are actually deployed in industry.

---

## 6. Suggested "Future Scope" points for your report

- Real-time push updates via WebSockets/Socket.IO instead of polling
- SMS/Email notifications to emergency contacts (Twilio/SMTP) when an alert is raised
- Map view with all active alerts plotted using Leaflet.js
- Role for multiple responder types (fire dept, police, ambulance) with routing
- Mobile app (React Native / Flutter) consuming the same Flask API

---

## 7. Default Login Reference

| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Citizen | *(register your own via `/register`)* | |
# Real-time SMS alerts

This project can send real SMS messages through Twilio. Before starting the app,
install the updated requirements and add your Twilio credentials to the local
`.env` file. Use `.env.example` as the safe-to-share template; `.env` is excluded
from Git. `ALERT_RECIPIENT_NUMBERS` accepts a comma-separated list of
emergency-control-room/mobile numbers in E.164 format, such as `+919876543210`.

On every citizen alert, all configured recipients receive the alert type, citizen
name, message, and Google Maps location link. When an administrator changes an
alert status, the citizen receives an SMS at the mobile number used during
registration. A Twilio trial account can only send to verified recipient numbers.

## Real-time email alerts

The app sends a responsive, mobile-friendly email immediately when an alert is created. Configure SMTP and
the `POLICE_EMAIL_RECIPIENTS`, `FIRE_EMAIL_RECIPIENTS`, `SOS_EMAIL_RECIPIENTS`,
and `OTHER_EMAIL_RECIPIENTS` lists in `.env`, using `.env.example` as the
template. Police and Fire alerts go to their matching list; SOS, Medical, and
Accident alerts go to the SOS list; Other alerts and standalone location shares
go to the Other list. Every email includes a Google Maps live-location link.

## Deploying to Vercel

This repository is ready for Vercel: `src/app.py` is the Flask function entry
point and `public/` contains the CDN-served CSS and JavaScript. Import the
repository into Vercel with the project root set to `emergency-alert-system`.
Then add the values from `.env.example` in **Settings → Environment Variables**;
never upload the local `.env` file.

Vercel Functions do not provide durable local disk storage. This deployment
uses a temporary SQLite database so the demo runs, but alert data can be reset
when a function is restarted. Use a managed PostgreSQL/MySQL database and set
`DATABASE_PATH`/database connection settings before using this for real cases.
