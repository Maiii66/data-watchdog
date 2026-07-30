import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import schedule

from alerts import warn
from lineage import who_is_affected

DATA_FILE = Path(__file__).parent / "data" / "orders.csv"
DB_FILE = Path(__file__).parent / "meta.db"

# Load the current CSV file and create a snapshot of its metadata.
def load_snapshot():
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        print(f"Data file not found: {DATA_FILE}")
        return None
    except Exception as exc:
        print(f"Failed to load data file: {exc}")
        return None

    ts = datetime.now().isoformat(sep=" ", timespec="seconds")
    row_count = len(df)
    columns = list(df.columns)
    null_counts = df.isna().sum().to_dict()
    return {
        "ts": ts,
        "row_count": row_count,
        "columns": columns,
        "null_counts": null_counts,
    }

# Ensure the snapshot history table exists in SQLite.
def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS history (ts TEXT, row_count INT, columns TEXT, null_counts TEXT)"
        )
        conn.commit()
        return conn
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        return None

# Save the current snapshot into the SQLite history table.
def save_snapshot(conn, snapshot):
    try:
        conn.execute(
            "INSERT INTO history (ts, row_count, columns, null_counts) VALUES (?, ?, ?, ?)",
            (
                snapshot["ts"],
                snapshot["row_count"],
                json.dumps(snapshot["columns"]),
                json.dumps(snapshot["null_counts"]),
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        print(f"Failed to save snapshot: {exc}")

# Load the most recent snapshots from the history table.
def load_history(conn, limit=30):
    try:
        cursor = conn.execute(
            "SELECT ts, row_count, columns, null_counts FROM history ORDER BY ts DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        history = []
        for ts, row_count, columns, null_counts in rows:
            history.append(
                {
                    "ts": ts,
                    "row_count": row_count,
                    "columns": json.loads(columns),
                    "null_counts": json.loads(null_counts),
                }
            )
        return history
    except sqlite3.Error as exc:
        print(f"Failed to load history: {exc}")
        return []

# Check whether the current row count is a significant volume anomaly.
def check_volume_anomaly(current, history):
    if len(history) < 5:
        return
    counts = np.array([snapshot["row_count"] for snapshot in history])
    mean = float(counts.mean())
    std = float(counts.std(ddof=0))
    if std == 0:
        if current["row_count"] != mean:
            warn(
                f"Row count anomaly! Today: {current['row_count']}, avg: {mean:.0f}, z-score: inf"
            )
        return
    z = (current["row_count"] - mean) / std
    if abs(z) > 2:
        warn(f"Row count anomaly! Today: {current['row_count']}, avg: {mean:.0f}, z-score: {z:.1f}")

# Check for schema changes compared to the previous snapshot.
def check_schema_change(current, history):
    if not history:
        return
    previous_columns = set(history[0]["columns"])
    current_columns = set(current["columns"])
    removed = previous_columns - current_columns
    added = current_columns - previous_columns
    if removed:
        warn(f"Columns REMOVED: {removed}")
    if added:
        warn(f"Columns ADDED: {added}")

# Check for null spikes in any column.
def check_null_spike(current):
    row_count = current["row_count"]
    if row_count == 0:
        return
    for column, null_count in current["null_counts"].items():
        pct = null_count / row_count * 100
        if pct > 20:
            warn(f"NULL spike in '{column}': {pct:.1f}% of rows are null!")

# Check whether the latest snapshot is stale compared to the previous one.
def check_freshness(current, history):
    if not history:
        return
    try:
        previous_ts = datetime.fromisoformat(history[0]["ts"])
        current_ts = datetime.fromisoformat(current["ts"])
    except ValueError:
        return
    if current_ts - previous_ts > timedelta(hours=2):
        warn("Data may be stale: last snapshot is more than 2 hours old.")

# Run all monitoring checks and report lineage.
def run():
    snapshot = load_snapshot()
    if snapshot is None:
        return

    print(f"--- Running checks at {snapshot['ts']} ---")

    conn = init_db()
    if conn is None:
        return

    history = load_history(conn)
    check_volume_anomaly(snapshot, history)
    check_schema_change(snapshot, history)
    check_null_spike(snapshot)
    check_freshness(snapshot, history)

    save_snapshot(conn, snapshot)
    conn.close()

    print("\nChecks done.")
    who_is_affected("orders.csv")


if __name__ == "__main__":
    run()

    # schedule.every(1).hours.do(run)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
