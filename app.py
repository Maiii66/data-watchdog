import json
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from checks import CheckRegistry
from config_loader import load_config, get_checks_config, get_sources_config, get_storage_config

config = load_config()
checks_cfg = get_checks_config(config)
storage_cfg = get_storage_config(config)
sources_cfg = get_sources_config(config)

app = Flask(__name__, static_folder="static", static_url_path="")

DB_FILE = Path(__file__).parent / storage_cfg["database"]

_registry = CheckRegistry()
_registry.load_from_config(checks_cfg)


def _get_conn():
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("PRAGMA table_info(history)")
    except Exception:
        pass
    return conn


def _source_names():
    return [s["name"] for s in sources_cfg]


def get_source_status(source_name):
    """Get status for a single source from history."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT ts, row_count, columns, null_counts FROM history "
            "WHERE source_name = ? ORDER BY ts DESC LIMIT 30",
            (source_name,),
        ).fetchall()
        conn.close()
    except Exception:
        return None

    if not rows:
        return {
            "name": source_name,
            "healthy": True,
            "row_count": 0,
            "columns": [],
            "alerts": [],
            "chart_data": [],
            "null_chart": [],
            "lineage": [],
            "total_snaps": 0,
            "snapshot_ts": "No data yet",
        }

    latest = rows[0]
    columns = json.loads(latest[2])
    null_counts = json.loads(latest[3])
    row_count = latest[1]

    current = {
        "ts": latest[0],
        "row_count": row_count,
        "columns": columns,
        "null_counts": null_counts,
    }

    history_dicts = []
    for ts, rc, cols, nulls in rows[1:]:
        history_dicts.append({
            "ts": ts,
            "row_count": rc,
            "columns": json.loads(cols),
            "null_counts": json.loads(nulls),
        })

    alerts = _registry.run_all(current, history_dicts)

    chart_data = [
        {"ts": r[0][11:16], "rows": r[1]}
        for r in reversed(rows[:15])
    ]
    null_chart = [
        {"col": col, "pct": round(cnt / row_count * 100, 1) if row_count > 0 else 0}
        for col, cnt in null_counts.items()
    ]

    source_cfg = next((s for s in sources_cfg if s["name"] == source_name), {})
    lineage = source_cfg.get("lineage", [])

    return {
        "name": source_name,
        "type": source_cfg.get("type", "unknown"),
        "healthy": len(alerts) == 0,
        "row_count": row_count,
        "columns": columns,
        "snapshot_ts": latest[0],
        "alerts": alerts,
        "chart_data": chart_data,
        "null_chart": null_chart,
        "lineage": lineage,
        "total_snaps": len(rows),
    }


@app.route("/")
def index():
    return send_from_directory("static", "dashboard.html")


@app.route("/api/status")
def status():
    sources = []
    for name in _source_names():
        sources.append(get_source_status(name))

    overall_healthy = all(s["healthy"] for s in sources) if sources else True
    total_alerts = sum(len(s["alerts"]) for s in sources)

    return jsonify({
        "healthy": overall_healthy,
        "total_alerts": total_alerts,
        "sources": sources,
    })


@app.route("/api/source/<source_name>")
def source_status(source_name):
    result = get_source_status(source_name)
    if result is None:
        return jsonify({"error": f"Source '{source_name}' not found"}), 404
    return jsonify(result)


@app.route("/api/run-monitor", methods=["POST"])
def run_monitor():
    try:
        from monitor import run
        run()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
