from flask import Flask, jsonify, send_from_directory
import sqlite3, json, subprocess
from datetime import datetime

app = Flask(__name__, static_folder="static", static_url_path="")

def get_history():
    try:
        conn = sqlite3.connect("meta.db")
        rows = conn.execute(
            "SELECT ts, row_count, columns, null_counts FROM history ORDER BY ts DESC LIMIT 30"
        ).fetchall()
        conn.close()
        return rows
    except:
        return []

@app.route("/")
def index():
    return send_from_directory("static", "dashboard.html")

@app.route("/api/status")
def status():
    history = get_history()
    if not history:
        return jsonify({"healthy": True, "row_count": 0, "columns": [],
                        "alerts": [], "chart_data": [], "null_chart": [],
                        "lineage": [], "total_snaps": 0,
                        "snapshot_ts": "No data yet"})

    latest = history[0]
    columns     = json.loads(latest[2])
    null_counts = json.loads(latest[3])
    row_count   = latest[1]

    # build alerts from real data
    alerts = []

    # volume check
    import numpy as np
    if len(history) >= 5:
        past = [r[1] for r in history[1:]]
        mean, std = np.mean(past), np.std(past)
        if std > 0:
            z = (row_count - mean) / std
            if abs(z) > 2:
                alerts.append({"type": "volume", "level": "error",
                    "text": f"Row count anomaly! Today: {row_count}, avg: {mean:.0f}, z-score: {z:.1f}"})

    # schema check
    if len(history) >= 2:
        prev_cols = set(json.loads(history[1][2]))
        curr_cols = set(columns)
        removed = prev_cols - curr_cols
        added   = curr_cols - prev_cols
        if removed:
            alerts.append({"type": "schema", "level": "error",
                "text": f"Columns REMOVED: {removed}"})
        if added:
            alerts.append({"type": "schema", "level": "warning",
                "text": f"New columns added: {added}"})

    # null check
    for col, count in null_counts.items():
        pct = count / row_count * 100 if row_count > 0 else 0
        if pct > 20:
            alerts.append({"type": "nulls", "level": "error",
                "text": f"NULL spike in '{col}': {pct:.1f}% of rows are null!"})

    chart_data = [
        {"ts": r[0][11:16], "rows": r[1]}
        for r in reversed(history[:15])
    ]
    null_chart = [
        {"col": col, "pct": round(cnt / row_count * 100, 1) if row_count > 0 else 0}
        for col, cnt in null_counts.items()
    ]

    return jsonify({
        "healthy":     len(alerts) == 0,
        "row_count":   row_count,
        "columns":     columns,
        "snapshot_ts": latest[0],
        "alerts":      alerts,
        "chart_data":  chart_data,
        "null_chart":  null_chart,
        "lineage":     ["Revenue Dashboard", "Marketing Report", "Fraud Detection Model"],
        "total_snaps": len(history),
    })

@app.route("/api/run-monitor", methods=["POST"])
def run_monitor():
    try:
        import monitor
        monitor.run()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
    