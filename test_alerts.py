"""Manual notification test for Data Watchdog.

Two modes:
  python test_alerts.py --quick   send a test Slack message + test email only.
  python test_alerts.py           full end-to-end: simulate volume/null/freshness
                                  anomalies through the real monitor -> notify
                                  -> Slack/email pipeline, then restore everything.

Run from the project root. Use --keep-fake-data to keep the anomalous CSV.
"""
import argparse
import csv
import json
import os
import random
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

from config_loader import (
    get_notifications_config,
    get_sources_config,
    load_config,
)

ROOT = Path(__file__).parent
DB_FILE = Path(__file__).parent / "meta.db"
CSV_FILE = Path(__file__).parent / "data" / "orders.csv"

BASELINE_COLUMNS = ["order_id", "customer", "amount", "status", "city", "created_at"]
ZERO_NULLS = {c: 0 for c in BASELINE_COLUMNS}
ANOMALOUS_ROWS = 400
BASELINE_ROWS = 200
NULL_FRACTION = 0.30


def _db_rows(conn, source_name):
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    sig = conn.execute("SELECT value FROM meta WHERE key='last_alert_sig'").fetchone()
    rows = conn.execute(
        "SELECT ts, row_count, columns, null_counts FROM history "
        "WHERE source_name = ? ORDER BY rowid",
        (source_name,),
    ).fetchall()
    return sig, rows


def _restore_rows(conn, source_name, sig, rows):
    conn.execute("DELETE FROM history WHERE source_name = ?", (source_name,))
    for ts, row_count, columns, null_counts in rows:
        conn.execute(
            "INSERT INTO history (source_name, ts, row_count, columns, null_counts) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_name, ts, row_count, columns, null_counts),
        )
    if sig is not None:
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('last_alert_sig', ?)",
            (sig[0],),
        )
    else:
        conn.execute("DELETE FROM meta WHERE key='last_alert_sig'")
    conn.commit()


def _clear_dedup_sig(conn):
    conn.execute("DELETE FROM meta WHERE key='last_alert_sig'")
    conn.commit()


def _seed_baseline(conn, source_name):
    conn.execute("DELETE FROM history WHERE source_name = ?", (source_name,))
    now = datetime.now()
    for i in range(6):
        ts = (now - timedelta(hours=5 - i * 0.3)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO history (source_name, ts, row_count, columns, null_counts) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                source_name,
                ts,
                BASELINE_ROWS,
                json.dumps(BASELINE_COLUMNS),
                json.dumps(ZERO_NULLS),
            ),
        )
    conn.commit()


def _write_anomalous_csv():
    fake = Faker()
    random.seed(7)
    records = []
    for i in range(1, ANOMALOUS_ROWS + 1):
        amount = round(
            fake.pydecimal(left_digits=4, right_digits=2, positive=True), 2
        )
        if random.random() < NULL_FRACTION:
            amount = ""
        records.append({
            "order_id": f"ORD{i:04d}",
            "customer": fake.name(),
            "amount": amount,
            "status": fake.random_element(
                elements=("completed", "pending", "cancelled", "returned")
            ),
            "city": fake.city(),
            "created_at": fake.date_time_between(
                start_date="-30d", end_date="now"
            ).strftime("%Y-%m-%d %H:%M:%S"),
        })
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BASELINE_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def quick_test():
    """Send a test Slack message and a test email. No data is changed."""
    print("\n=== Quick notification test ===\n")
    config = load_config()
    notifications = get_notifications_config(config)

    slack_cfg = notifications["slack"]
    if slack_cfg["enabled"] and slack_cfg["webhook_url"]:
        from notify import send_slack
        ok = send_slack(
            slack_cfg["webhook_url"],
            ":white_check_mark: Hello from Data Watchdog - this is a manual "
            "notification test to verify Slack is working.",
        )
        print(f"[{'OK' if ok else 'FAIL'}] Slack test message")
    else:
        print("[SKIP] Slack is not configured (SLACK_WEBHOOK_URL missing)")

    email_cfg = notifications["email"]
    if email_cfg["enabled"] and email_cfg["to"]:
        from notify import send_email
        ok = send_email(
            email_cfg,
            "[Data Watchdog] Manual notification test",
            "Hello,\n\nThis is a test email from Data Watchdog to confirm email "
            "notifications are working.\n\nIf you received this, everything is "
            "configured correctly.\n\n- Data Watchdog",
        )
        print(f"[{'OK' if ok else 'FAIL'}] Email test message to {', '.join(email_cfg['to'])}")
    else:
        print("[SKIP] Email is not configured (SMTP settings missing)")

    print("\n=== Quick test finished ===\n")


def run_full_test(src_name="orders_csv", keep_fake_data=False):
    """Simulate real data-quality anomalies and send a Slack + email alert."""
    print("\n=== Full end-to-end Data Watchdog test ===\n")

    csv_backup = None
    if CSV_FILE.exists():
        fd, csv_backup = tempfile.mkstemp(prefix="orders_backup_", suffix=".csv")
        os.close(fd)
        shutil.copy2(CSV_FILE, csv_backup)
    else:
        print("[WARN] data/orders.csv not found - creating it for the test")

    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS history ("
                 "source_name TEXT, ts TEXT, row_count INT, "
                 "columns TEXT, null_counts TEXT)")
    conn.commit()
    sig_before, rows_before = _db_rows(conn, src_name)
    conn.close()

    wrote_csv = False
    try:
        _write_anomalous_csv()
        wrote_csv = True
        print(f"Wrote anomalous CSV: {ANOMALOUS_ROWS} rows, ~{int(NULL_FRACTION*100)}% blank 'amount'")

        conn = sqlite3.connect(DB_FILE)
        _seed_baseline(conn, src_name)
        _clear_dedup_sig(conn)
        conn.close()
        print("Seeded baseline history (6 x 200-row snapshots) and cleared dedup marker")

        from monitor import run_source
        sources_cfg = get_sources_config(load_config())
        all_alerts = {}
        for cfg in sources_cfg:
            name = cfg.get("name", "unknown")
            all_alerts[name] = run_source(cfg)

        total = sum(len(a) for a in all_alerts.values())
        print(f"\n=== Monitor finished: {total} alert(s) across {len(sources_cfg)} source(s). ===")

        results = None
        if total > 0:
            from notify import notify
            results = notify(all_alerts)
            print("\nNotification results:")
            for channel, ok in results.items():
                status = "OK" if ok is True else "FAIL" if ok is False else "skipped"
                print(f"  - {channel}: {status}")
        else:
            print("No alerts detected - nothing was sent. Check your data/config.")

        return results
    finally:
        if conn is not None:
            conn.close()
        conn = sqlite3.connect(DB_FILE)
        _restore_rows(conn, src_name, sig_before, rows_before)
        conn.close()
        print("\nRestored the snapshot history for " + src_name)

        if wrote_csv and csv_backup and not keep_fake_data:
            shutil.copy2(csv_backup, CSV_FILE)
            print("Restored the original data/orders.csv")
        elif keep_fake_data:
            print("[WARN] --keep-fake-data: leaving the anomalous CSV in place")
        if csv_backup:
            Path(csv_backup).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Manual notification test for Data Watchdog")
    parser.add_argument("--quick", action="store_true",
                        help="send a test Slack + email only (no data changes)")
    parser.add_argument("--keep-fake-data", action="store_true",
                        help="keep the anomalous CSV after the full test")
    args = parser.parse_args()

    if args.quick:
        quick_test()
    else:
        run_full_test(keep_fake_data=args.keep_fake_data)


if __name__ == "__main__":
    main()