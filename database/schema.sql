-- Emergency Alert System Database Schema
-- Works with SQLite (used by app.py) — MySQL-compatible version notes included as comments

CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(100),
    phone         VARCHAR(15),
    role          VARCHAR(10) DEFAULT 'citizen' CHECK(role IN ('citizen', 'admin')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emergency_alerts (
    alert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    alert_type   VARCHAR(20) NOT NULL CHECK(alert_type IN ('Medical','Fire','Police','Accident','Other')),
    message      TEXT,
    latitude     DECIMAL(10,8),
    longitude    DECIMAL(11,8),
    status       VARCHAR(15) DEFAULT 'Pending' CHECK(status IN ('Pending','Acknowledged','Resolved')),
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS responders (
    responder_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id      INTEGER NOT NULL,
    admin_id      INTEGER NOT NULL,
    action_taken  VARCHAR(255),
    responded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_id) REFERENCES emergency_alerts(alert_id),
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);

-- A location share is separate from an emergency alert.  This preserves a
-- small audit trail when a citizen chooses to share their current position
-- without creating a second SOS case.
CREATE TABLE IF NOT EXISTS location_shares (
    location_share_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    latitude          DECIMAL(10,8) NOT NULL,
    longitude         DECIMAL(11,8) NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Default admin account (username: admin / password: admin123)
-- Password hash is generated at first run by app.py (see seed_admin() in app.py)
