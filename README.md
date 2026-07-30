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

> Status: actively in development. See [Roadmap](#roadmap) below for what's built vs. planned.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/data-watchdog.git
cd data-watchdog
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

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

## Screenshot

_(add a screenshot or GIF of the dashboard here once Milestone 1 is done)_

## Project structure

```
data-watchdog/
├── generate_data.py   # creates sample/fake order data
├── monitor.py         # runs checks, stores snapshot history
├── alerts.py          # formats and sends alerts
├── lineage.py         # maps data sources to downstream systems
├── dashboard.html     # visual dashboard
├── data/              # generated data (gitignored)
└── requirements.txt
```

## Roadmap

- [ ] Wire dashboard to live backend (Flask API reading from real snapshot history)
- [ ] Move hardcoded settings into a config file
- [ ] Support additional data sources (databases, cloud storage)
- [ ] Smarter statistics (median/MAD instead of mean/std, seasonal baselines)
- [ ] Distribution drift & duplicate-row checks
- [ ] Slack/email alerting with severity levels and deduplication
- [ ] Auto-derived lineage instead of a static map
- [ ] Docker support, CI, and test coverage

## Contributing

This is a learning project I'm actively building in public. Issues and suggestions welcome.

## License

MIT — see [LICENSE](LICENSE).
