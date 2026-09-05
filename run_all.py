"""One-command launcher for Data Watchdog.

Runs the real monitor (all checks against all configured data sources),
notifies via Slack/email when real issues are found, then starts the
dashboard and opens it in the browser.

Usage:
  python run_all.py
"""
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent
DASHBOARD_URL = "http://127.0.0.1:5000"
PORT = 5000


def run_real_monitor():
    """Run all checks against real data and notify if real issues exist."""
    from config_loader import get_sources_config, load_config
    from monitor import run_source
    from notify import notify

    sources_cfg = get_sources_config(load_config())
    all_alerts = {}
    for cfg in sources_cfg:
        name = cfg.get("name", "unknown")
        all_alerts[name] = run_source(cfg)

    total = sum(len(a) for a in all_alerts.values())
    print(f"\n=== Monitor finished: {total} alert(s) across {len(sources_cfg)} source(s). ===")

    if total > 0:
        results = notify(all_alerts)
        print("\nNotification results:")
        for channel, ok in results.items():
            status = "OK" if ok is True else "FAIL" if ok is False else "skipped (unchanged alerts)"
            print(f"  - {channel}: {status}")
    else:
        print("No issues found - nothing to send.")


def _port_in_use(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    print("=== Data Watchdog - running all checks on your data ===\n")
    run_real_monitor()

    print("\n=== Starting the dashboard ===\n")

    if _port_in_use(PORT):
        print(f"[OK] Dashboard already running at {DASHBOARD_URL}")
        webbrowser.open(DASHBOARD_URL)
        return

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "app.py")],
        cwd=str(ROOT),
    )

    time.sleep(2)
    print(f"Dashboard should be available at {DASHBOARD_URL}")
    webbrowser.open(DASHBOARD_URL)

    print("\nDashboard is running. Press Ctrl+C to stop it.\n")
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping dashboard...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()