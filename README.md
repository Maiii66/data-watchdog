# Data Watchdog

A lightweight data observability tool that monitors datasets for quality issues — row count anomalies, schema changes, null spikes, and stale data — and alerts when something looks wrong.

Started as a small script to learn how tools like Monte Carlo / Bigeye work under the hood. Being actively rebuilt into a real, deployable tool: live dashboard, configurable checks, Slack alerts, and real lineage tracking.

## Why

Data pipelines break silently all the time — a column gets dropped, a source goes stale, a job returns 40 rows instead of 20,000 — and nobody finds out until a dashboard downstream looks wrong. This project detects that automatically and tells you before your stakeholders do.

## Features

- **Volume anomaly detection** — flags row counts that deviate significantly from historical norms
- **Schema change detection** — flags added/removed columns between runs
- **Null spike detection** — flags columns with abnormally high null rates
- **Freshness checks** — flags data that hasn't been updated recently
- **Snapshot history** — every run is stored so trends can be tracked over time
- **Lineage awareness** — shows which downstream systems are affected when a source breaks
- **Live dashboard** — visualizes health status, alert history, and trends
- **Automatic scheduling** — checks run on a configurable interval (e.g. every 30 min)
- **Slack + email alerts** — notify on anomalies, with deduplication so you aren't spammed on persistent issues

> Status: actively in development. See [Roadmap](#roadmap) below for what's built vs. planned.

## Setup    

```bash
git clone https://github.com/Maiii66/data-watchdog.git
cd data-watchdog
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # then fill in your real values
```

### Scheduling & notifications

- **Schedule** — `config.yaml → schedule` (set `enabled: true`, `interval: 30m`). The web app starts an in-process scheduler on boot; runs are locked so scheduled and manual runs never overlap.
- **Slack** — create an Incoming Webhook at `api.slack.com/apps`, put the URL in `.env` as `SLACK_WEBHOOK_URL`.
- **Email** — set `SMTP_USER` / `SMTP_PASS` (use an app password for Gmail), `SMTP_FROM`, and `ALERT_EMAIL` in `.env`.
- Channels are active only when enabled in `config.yaml` **and** the matching `.env` value is present. Missing/empty secrets silently disable that channel instead of crashing.
- Only new/changed alert sets trigger notifications (deduplication), so a persistently broken source won't email you every 30 minutes. `.env` is gitignored — secrets never end up in history.

## Usage

Generate sample data:
```bash
python generate_data.py
```

Run a check:
```bash
python monitor.py
```

Simulate a broken pipeline (dropped column, nulls, low row count):
```python
# in generate_data.py __main__ block
generate_data(break_it=True)
```
then re-run `python generate_data.py && python monitor.py`.

## Manual testing (Slack + email)

Run these from the project root with the venv Python:

```bash
# 1. Quick check - just verify Slack + email are working (no data changes)
venv\Scripts\python.exe test_alerts.py --quick

# 2. Full test - simulate volume / null / freshness anomalies, send a real
#    Slack + email alert, then restore your data automatically
venv\Scripts\python.exe test_alerts.py

# 3. Everything + dashboard - run the real monitor (all checks on your real
#    data), notify if real issues are found, then start the dashboard and open
#    it in your browser
venv\Scripts\python.exe run_all.py
```

- `test_alerts.py --quick` sends a test Slack message and a test email using your `.env` settings.
- `test_alerts.py` seeds fake baseline history, writes a broken `data/orders.csv` (400 rows, ~30% blank `amount`), runs the real monitor (which fires the Slack/email alerts), then restores your original CSV and history.
- `run_all.py` runs the real monitor against all configured sources, sends Slack/email only if real issues are found, then starts the Flask dashboard (`app.py`) at `http://localhost:5000`.

## Screenshot

_(add a screenshot or GIF of the dashboard here once Milestone 1 is done)_

## Project structure

```
data-watchdog/
├── config.yaml        # sources, checks, storage, schedule, notifications
├── config_loader.py   # loads/validates config, expands ${ENV} vars
├── generate_data.py   # creates sample/fake order data
├── monitor.py         # runs checks, stores snapshot history, triggers alerts
├── alerts.py          # console alert formatting
├── notify.py          # Slack + email alert delivery with dedup
├── app.py             # Flask backend + scheduler
├── sources.py         # data source adapters (CSV, PostgreSQL)
├── checks/            # registry + individual quality checks
├── static/            # dashboard UI
├── scripts/           # postgres seed SQL
├── tests/             # pytest test suite
├── data/              # generated data (gitignored)
└── requirements.txt
```

## Roadmap

- [x] Wire dashboard to live backend (Flask API reading from real snapshot history)
- [x] Move hardcoded settings into a config file
- [x] Support additional data sources (databases, cloud storage) — PostgreSQL + CSV
- [x] Slack/email alerting with severity levels and deduplication
- [x] Docker support, CI, and test coverage — Docker compose for Postgres; tests in progress
- [ ] Smarter statistics (median/MAD instead of mean/std, seasonal baselines)
- [ ] Distribution drift & duplicate-row checks
- [ ] Auto-derived lineage instead of a static map
- [ ] True scheduling in production (systemd/cron/Task Scheduler) — in-app scheduler works while the web app runs

## Contributing

This is a learning project I'm actively building in public. Issues and suggestions welcome.

## License

MIT — see [LICENSE](LICENSE).
