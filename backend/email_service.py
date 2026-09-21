"""Immediate SMTP notifications for emergency alerts.

Recipient groups are configured in the project's .env file.  No SMTP secrets
or recipient addresses are sent to the browser.
"""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape


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


def send_email(recipient, subject, text_body, html_body):
    """Send a multipart emergency email. Returns a safe error on failure."""
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
    email.set_content(text_body)
    email.add_alternative(html_body, subtype="html")

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


def build_alert_email_html(
    alert_type, message, reporter_name, maps_link, *, alert_id=None,
    reporter_phone=None, reporter_username=None, latitude=None, longitude=None,
):
    """Create a safe, responsive HTML emergency-alert email."""
    label = "SOS" if (message or "").strip().upper().startswith("SOS:") else alert_type.upper()
    alert_ref = f"#{alert_id}" if alert_id is not None else "New alert"
    reported_at = datetime.now().astimezone().strftime("%d %b %Y, %I:%M %p %Z")
    if latitude is not None and longitude is not None:
        coordinates = f"{latitude:.6f}, {longitude:.6f}"
        location_content = f'''<p class="detail-label">LIVE LOCATION</p><p class="coordinates">{escape(coordinates)}</p><a class="map-button" href="{escape(maps_link, quote=True)}">Open live location in Google Maps &#8594;</a>'''
    else:
        location_content = '<p class="detail-label">LIVE LOCATION</p><p class="unavailable">Location was not available when this alert was sent.</p>'

    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Emergency alert {escape(alert_ref)}</title><style>
body{{margin:0;padding:0;background:#f1f5f9;color:#172033;font-family:Arial,Helvetica,sans-serif}}.wrap{{width:100%;padding:28px 12px;box-sizing:border-box}}.card{{max-width:620px;margin:0 auto;overflow:hidden;background:#fff;border-radius:18px;box-shadow:0 12px 36px rgba(15,23,42,.14)}}.hero{{padding:30px 32px 26px;background:linear-gradient(135deg,#b91c1c,#ef4444);color:#fff}}.eyebrow{{margin:0 0 10px;font-size:12px;font-weight:700;letter-spacing:1.5px;opacity:.88}}h1{{margin:0;font-size:27px;line-height:1.2}}.alert-ref{{margin:10px 0 0;font-size:15px;opacity:.95}}.content{{padding:30px 32px 12px}}.badge{{display:inline-block;border-radius:999px;padding:7px 12px;background:#fef2f2;color:#b91c1c;font-size:12px;font-weight:700;letter-spacing:.7px}}.detail-label{{margin:26px 0 6px;color:#64748b;font-size:11px;font-weight:700;letter-spacing:1.2px}}.detail-value{{margin:0;font-size:16px;line-height:1.55;white-space:pre-wrap}}.reporter{{padding:16px;border-radius:12px;background:#f8fafc}}.reporter p{{margin:4px 0;line-height:1.45}}.coordinates{{margin:0 0 16px;font-size:16px;font-weight:700}}.map-button{{display:inline-block;padding:13px 17px;border-radius:9px;background:#0f766e;color:#fff!important;text-decoration:none;font-size:14px;font-weight:700}}.unavailable{{margin:0;color:#9a3412;line-height:1.5}}.footer{{padding:22px 32px 28px;color:#64748b;font-size:12px;line-height:1.5}}@media screen and (max-width:480px){{.wrap{{padding:0}}.card{{border-radius:0}}.hero,.content,.footer{{padding-left:22px;padding-right:22px}}h1{{font-size:23px}}}}</style></head><body><div class="wrap"><main class="card"><section class="hero"><p class="eyebrow">WE CARE 24x7 &bull; RESPONSE REQUIRED</p><h1>Emergency alert received</h1><p class="alert-ref">{escape(alert_ref)} &middot; {escape(reported_at)}</p></section><section class="content"><span class="badge">{escape(label)} EMERGENCY</span><p class="detail-label">ALERT DETAILS</p><p class="detail-value">{escape(message or 'No additional details')}</p><p class="detail-label">REPORTER</p><div class="reporter"><p><strong>{escape(reporter_name or 'Unknown citizen')}</strong></p><p>Account: {escape(reporter_username or 'Not provided')}</p><p>Callback: {escape(reporter_phone or 'Not provided')}</p></div>{location_content}</section><footer class="footer">This is an automated emergency notification. Please follow your response protocol immediately.</footer></main></div></body></html>'''


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
    html_body = build_alert_email_html(
        alert_type, message, reporter_name, maps_link, alert_id=alert_id,
        reporter_phone=reporter_phone, reporter_username=reporter_username,
        latitude=latitude, longitude=longitude,
    )

    delivered, errors = 0, []
    for recipient in recipients:
        sent, error = send_email(recipient, subject, body, html_body)
        if sent:
            delivered += 1
        elif error:
            errors.append(error)
    return delivered, list(dict.fromkeys(errors))
