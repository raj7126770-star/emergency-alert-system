"""Immediate SMTP notifications for emergency alerts.

Recipient groups are configured in the project's .env file.  No SMTP secrets
or recipient addresses are sent to the browser.
"""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage


def _addresses(value):
    return [address.strip() for address in value.split(",") if address.strip()]


def recipients_for_alert(alert_type, message):
    """Choose the control-room inboxes responsible for this kind of alert."""
    if (message or "").strip().upper().startswith("SOS:"):
        setting = "SOS_EMAIL_RECIPIENTS"
    elif alert_type == "Police":
        setting = "POLICE_EMAIL_RECIPIENTS"
    elif alert_type == "Fire":
        setting = "FIRE_EMAIL_RECIPIENTS"
    elif alert_type in ("Medical", "Accident"):
        setting = "SOS_EMAIL_RECIPIENTS"
    else:
        setting = "OTHER_EMAIL_RECIPIENTS"
    return _addresses(os.environ.get(setting, "")), setting


def send_email(recipient, subject, body):
    """Send one plain-text SMTP email. Returns a safe error message on failure."""
    host = os.environ.get("SMTP_HOST")
    sender = os.environ.get("SMTP_FROM_EMAIL")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    try:
        port = int(os.environ.get("SMTP_PORT", "465"))
    except ValueError:
        return False, "SMTP_PORT must be a number."

    if not all((host, sender, username, password)):
        return False, "Email is not configured on the server."

    email = EmailMessage()
    email["From"] = sender
    email["To"] = recipient
    email["Subject"] = subject
    email.set_content(body)

    try:
        if os.environ.get("SMTP_USE_SSL", "true").lower() in ("1", "true", "yes"):
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(username, password)
                server.send_message(email)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(email)
        return True, None
    except (OSError, smtplib.SMTPException):
        return False, "Email delivery failed. Check the SMTP configuration."


def notify_alert_by_email(
    alert_type, message, reporter_name, maps_link,
    *, alert_id=None, reporter_phone=None, reporter_username=None,
    latitude=None, longitude=None,
):
    """Immediately email the responsible emergency mailbox(es) with full,
    actionable detail: who reported it, how to reach them, exact
    coordinates (not just the map link), and when it came in.
    """
    recipients, setting = recipients_for_alert(alert_type, message)
    if not recipients:
        return 0, [f"No recipients configured in {setting}."]

    label = "SOS" if (message or "").strip().upper().startswith("SOS:") else alert_type.upper()
    subject = f"[WE CARE 24x7] {label} EMERGENCY ALERT"
    if alert_id is not None:
        subject += f" #{alert_id}"

    if latitude is not None and longitude is not None:
        coords_line = f"Coordinates: {latitude:.6f}, {longitude:.6f}"
    else:
        coords_line = "Coordinates: not available"

    lines = ["EMERGENCY ALERT", ""]
    if alert_id is not None:
        lines.append(f"Alert ID: {alert_id}")
    lines.append(f"Type: {alert_type}")
    lines.append(f"Reported at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"Reporter: {reporter_name}")
    if reporter_username:
        lines.append(f"Account: {reporter_username}")
    lines.append(f"Callback phone: {reporter_phone or 'Not provided'}")
    lines.append("")
    lines.append(f"Details: {message or 'No additional details'}")
    lines.append("")
    lines.append(coords_line)
    lines.append(f"Map link: {maps_link}")
    body = "\n".join(lines) + "\n"

    delivered, errors = 0, []
    for recipient in recipients:
        sent, error = send_email(recipient, subject, body)
        if sent:
            delivered += 1
        elif error:
            errors.append(error)
    return delivered, list(dict.fromkeys(errors))
