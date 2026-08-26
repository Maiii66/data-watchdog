import json
import sqlite3
from datetime import datetime
from pathlib import Path

from alerts import warn
from checks import CheckRegistry
from config_loader import load_config, get_checks_config, get_sources_config, get_storage_config
from sources import get_source

config = load_config()
checks_cfg = get_checks_config(config)
sources_cfg = get_sources_config(config)
storage_cfg = get_storage_config(config)

DB_FILE = Path(__file__).parent / storage_cfg["database"]
HISTORY_LIMIT = storage_cfg["history_limit"]

_registry = CheckRegistry()
_registry.load_from_config(checks_cfg)


def load_snapshot(source):
    """Load a snapshot from any source type via the source adapter."""
    try:
        df = source.load()
    except Exception as exc:
        print(f"Failed to load source '{source.name}': {exc}")
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


def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS history ("
            "source_name TEXT, ts TEXT, row_count INT, "
            "columns TEXT, null_counts TEXT)"
        )
        conn.commit()
        return conn
    except sqlite3.Error as exc:
        print(f"Database error: {exc}")
        return None


def _ensure_source_column(conn):
    """Add source_name column to old tables that don't have it."""
    try:
        cursor = conn.execute("PRAGMA table_info(history)")
        cols = [row[1] for row in cursor.fetchall()]
        if "source_name" not in cols:
            conn.execute("ALTER TABLE history ADD COLUMN source_name TEXT DEFAULT ''")
            conn.commit()
    except sqlite3.Error:
        pass


def save_snapshot(conn, source_name, snapshot):
    try:
        conn.execute(
            "INSERT INTO history (source_name, ts, row_count, columns, null_counts) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                source_name,
                snapshot["ts"],
                snapshot["row_count"],
                json.dumps(snapshot["columns"]),
                json.dumps(snapshot["null_counts"]),
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        print(f"Failed to save snapshot: {exc}")


def load_history(conn, source_name, limit=None):
    if limit is None:
        limit = HISTORY_LIMIT
    try:
        cursor = conn.execute(
            "SELECT ts, row_count, columns, null_counts FROM history "
            "WHERE source_name = ? ORDER BY ts DESC LIMIT ?",
            (source_name, limit),
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


def run_source(source_cfg):
    """Run checks for a single data source. Returns list of alerts."""
    source = get_source(source_cfg)
    source_name = source_cfg["name"]

    snapshot = load_snapshot(source)
    if snapshot is None:
        return []

    print(f"\n--- [{source_name}] Running checks at {snapshot['ts']} ---")

    conn = init_db()
    if conn is None:
        return []

    _ensure_source_column(conn)
    history = load_history(conn, source_name)
    alerts = _registry.run_all(snapshot, history)

    for a in alerts:
        warn(f"[{source_name}] {a['text']}")

    save_snapshot(conn, source_name, snapshot)
    conn.close()

    lineage = source_cfg.get("lineage", [])
    if lineage and alerts:
        print(f"\n  Downstream systems at risk ({source_name}):")
        for system in lineage:
            print(f"    - {system}")

    return alerts


def run():
    """Run checks across all configured data sources."""
    all_alerts = {}
    for source_cfg in sources_cfg:
        source_name = source_cfg.get("name", "unknown")
        alerts = run_source(source_cfg)
        all_alerts[source_name] = alerts

    total = sum(len(a) for a in all_alerts.values())
    print(f"\n=== All checks done. {total} alert(s) across {len(sources_cfg)} source(s). ===")
    return all_alerts


if __name__ == "__main__":
    run()
