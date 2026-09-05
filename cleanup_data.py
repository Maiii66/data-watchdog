"""Reset Data Watchdog back to a clean state.

Regenerates a clean sample orders.csv, clears the contaminated orders_csv
snapshot history in meta.db, and removes the notification dedup marker so the
baseline starts fresh.

Usage:
  python cleanup_data.py
"""
import sqlite3
from pathlib import Path

from generate_data import generate_data

ROOT = Path(__file__).parent
DB_FILE = ROOT / "meta.db"


def main():
    print("=== Data Watchdog cleanup ===\n")

    generate_data()
    print("Regenerated clean data/orders.csv (200 rows, 6 columns, no nulls)")

    conn = sqlite3.connect(DB_FILE)
    try:
        deleted = conn.execute(
            "DELETE FROM history WHERE source_name = 'orders_csv'"
        ).rowcount
        conn.execute("DELETE FROM meta WHERE key = 'last_alert_sig'")
        conn.commit()
        print(f"Cleared {deleted} orders_csv snapshot(s) from meta.db")
        print("Cleared the notification dedup marker")
    finally:
        conn.close()

    print("\nCleanup done - run 'run_all' or 'python monitor.py' to start a fresh baseline.")


if __name__ == "__main__":
    main()