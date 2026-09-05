import hashlib
import json
import smtplib
import sqlite3
import urllib.request
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path

from config_loader import get_notifications_config, get_storage_config, load_config


def alert_signature(all_alerts):
    """Stable hash of the current alert set, used for deduplication."""
    parts = sorted(
        (
            src,
            sorted(
                f"{a.get('type')}|{a.get('level')}|{a.get('text')}"
                for a in alerts
            ),
        )
        for src, alerts in all_alerts.items()
    )
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _db_file():
    config = load_config()
    storage = get_storage_config(config)
    return Path(__file__).parent / storage["database"]


def _load_last_sig():
    db = _db_file()
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT value FROM meta WHERE key = 'last_alert_sig'"
        ).fetchall()
        conn.close()
        return rows[0][0] if rows else None
    except sqlite3.Error:
        return None


def _save_last_sig(sig):
    db = _db_file()
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_alert_sig', ?)",
            (sig,),
        )
        conn.commit()
    finally:
        conn.close()


def send_slack(webhook_url, text):
    """POST a message to a Slack incoming webhook. Returns True on success."""
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
        return True
    except Exception as exc:
        print(f"Slack notification failed: {exc}")
        return False


def send_email(cfg, subject, body):
    """Send an alert email via SMTP. Returns True on success."""
    if not cfg.get("from") or not cfg.get("to"):
        print("Email notification skipped: missing from/to address")
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = cfg["from"]
        msg["To"] = ", ".join(cfg["to"])
        msg["Date"] = formatdate(localtime=True)
        with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=30) as server:
            if cfg.get("use_tls"):
                server.starttls()
            if cfg.get("username") and cfg.get("password"):
                server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from"], cfg["to"], msg.as_string())
        return True
    except Exception as exc:
        print(f"Email notification failed: {exc}")
        return False


def build_slack_text(all_alerts):
    """Render alerts as a Slack message. Returns None when there are none."""
    lines = []
    for source, alerts in all_alerts.items():
        for a in alerts:
            level = a.get("level", "info").upper()
            alert_type = a.get("type", "unknown")
            text = a.get("text", "")
            lines.append(f"[{source}] *{level}* ({alert_type}): {text}")
    if not lines:
        return None
    lines.insert(
        0,
        f":rotating_light: *Data Watchdog* - {len(lines)} anomaly/anomalies detected at "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )
    return "\n".join(lines)


_SOURCE_LABELS = {
    "orders_csv": "the orders data",
    "orders_pg": "the orders database",
    "sales_data_pg": "the sales data",
}


def _plain_source_label(source):
    """Return a human-friendly, easy-to-read name for a data source."""
    return _SOURCE_LABELS.get(source, f"the {source} data")


def _plain_message(source, alert):
    """Translate a technical alert into plain, easy-to-understand wording."""
    alert_type = alert.get("type", "unknown")
    text = alert.get("text", "")

    if alert_type == "volume":
        return (
            f"The number of records in {_plain_source_label(source)} changed "
            f"suddenly. It is much higher or lower than usual, which may mean "
            f"data was duplicated, lost, or not fully received."
        )
    if alert_type == "nulls":
        return (
            f"Some information is missing in {_plain_source_label(source)}. "
            f"One or more fields are blank more often than we expect, so some "
            f"records are incomplete."
        )
    if alert_type == "freshness":
        return (
            f"{_plain_source_label(source).capitalize()} has not been updated "
            f"recently (more than 2 hours). The information may be out of date."
        )
    if alert_type == "schema":
        return (
            f"The structure of {_plain_source_label(source)} changed - some "
            f"fields were added or removed. This can affect the reports that "
            f"depend on it."
        )
    plain = text.lower().strip(" .")
    return f"An issue was found in {_plain_source_label(source)}: {plain}."


def build_email(all_alerts):
    """Render alerts as an email (subject, body). Returns None when clean.

    The email is written in plain, easy-to-understand language so anyone can
    understand it. A short 'Technical details' section at the bottom keeps the
    original raw alerts for engineers.
    """
    plain_lines = []
    detail_lines = []
    for source, alerts in all_alerts.items():
        for a in alerts:
            plain_lines.append(f"- {_plain_message(source, a)}")
            level = a.get("level", "info").upper()
            alert_type = a.get("type", "unknown")
            detail_lines.append(f"- [{source}] [{level}] ({alert_type}) {a.get('text')}")
    if not plain_lines:
        return None

    total = sum(len(a) for a in all_alerts.values())
    subject = f"[Data Watchdog] {total} possible data issue(s) found"

    body_lines = [
        "Hello,",
        "",
        "Our automated data check found a few things that need your attention.",
        "",
        *plain_lines,
        "",
        "If anything looks wrong, please reach out to your data team.",
        "",
        "--------------------------------------------",
        "Technical details (for your engineering team)",
        "--------------------------------------------",
        *detail_lines,
        "",
        "This message was generated automatically by Data Watchdog.",
    ]
    return subject, "\n".join(body_lines)


def notify(all_alerts):
    """Send alerts to enabled channels with deduplication.

    Args:
        all_alerts: dict of {source_name: [alert dicts, ...]}

    Returns:
        dict with keys 'slack' and 'email' mapping to True if sent,
        or None when skipped/failed.
    """
    if not all_alerts or not any(all_alerts.values()):
        return {"slack": None, "email": None}

    config = load_config()
    notifications = get_notifications_config(config)

    sig = alert_signature(all_alerts)
    if sig == _load_last_sig():
        print("Notifications skipped: alert set unchanged since last run")
        return {"slack": None, "email": None}

    delivered = False
    results = {}

    slack_cfg = notifications["slack"]
    if slack_cfg["enabled"] and slack_cfg["webhook_url"]:
        text = build_slack_text(all_alerts)
        if text:
            ok = send_slack(slack_cfg["webhook_url"], text)
            results["slack"] = ok
            delivered = delivered or ok

    email_cfg = notifications["email"]
    if email_cfg["enabled"]:
        built = build_email(all_alerts)
        if built:
            subject, body = built
            ok = send_email(email_cfg, subject, body)
            results["email"] = ok
            delivered = delivered or ok

    if any(results.get(k) for k in ("slack", "email")):
        _save_last_sig(sig)

    return results