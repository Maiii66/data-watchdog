import os
import re
from pathlib import Path

from dotenv import load_dotenv
import yaml

CONFIG_FILE = Path(__file__).parent / "config.yaml"

_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


def _expand_env(value, required=None):
    """Replace ${VAR} references with environment variable values.

    Args:
        value: string/dict/list to expand.
        required: set of variable names that must be set. Missing variables
            outside this set expand to an empty string so optional channels
            (Slack, email, etc.) can be disabled without crashes.
    """
    required = required or set()
    if isinstance(value, str):
        def replacer(match):
            env_val = os.environ.get(match.group(1))
            if env_val is None:
                if match.group(1) in required:
                    raise ValueError(f"Environment variable {match.group(1)} is not set")
                return ""
            return env_val
        return _ENV_PATTERN.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env(v, required) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(item, required) for item in value]
    return value


def _validate(data):
    """Validate required config structure and return a list of errors."""
    errors = []

    if "data_sources" not in data:
        errors.append("Missing required section: data_sources")
    elif not isinstance(data["data_sources"], list) or len(data["data_sources"]) == 0:
        errors.append("data_sources must be a non-empty list")
    else:
        for i, source in enumerate(data["data_sources"]):
            if "name" not in source:
                errors.append(f"data_sources[{i}] missing required field: name")
            source_type = source.get("type", "csv")
            if source_type == "csv" and "file" not in source:
                errors.append(f"data_sources[{i}] type=csv but missing required field: file")
            if source_type == "postgres" and "connection_string" not in source:
                errors.append(f"data_sources[{i}] type=postgres but missing required field: connection_string")
            if source_type == "postgres" and "table" not in source:
                errors.append(f"data_sources[{i}] type=postgres but missing required field: table")

    if "checks" not in data:
        errors.append("Missing required section: checks")

    return errors


def load_config(path=None):
    """Load and validate the config file. Returns parsed config dict."""
    config_path = Path(path) if path else CONFIG_FILE

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    load_dotenv(config_path.parent / ".env")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        raise ValueError(f"Config file is empty: {config_path}")

    errors = _validate(data)
    if errors:
        raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    data = _expand_env(
        data,
        required={"DB_USER", "DB_PASS", "DB_NAME", "DB_HOST", "DB_PORT"},
    )
    return data


def get_checks_config(config):
    """Return the checks section with sensible defaults."""
    checks = config.get("checks", {})
    defaults = {
        "volume_anomaly": {"enabled": True, "z_threshold": 2.0, "min_history": 5},
        "schema_change": {"enabled": True},
        "null_spike": {"enabled": True, "threshold_pct": 20.0},
        "freshness": {"enabled": True, "max_hours": 2},
    }
    merged = {}
    for name, default in defaults.items():
        user = checks.get(name, {})
        merged[name] = {**default, **user}
    return merged


def get_sources_config(config):
    """Return the data_sources list."""
    return config.get("data_sources", [])


def get_storage_config(config):
    """Return storage settings with defaults."""
    storage = config.get("storage", {})
    return {
        "database": storage.get("database", "meta.db"),
        "history_limit": storage.get("history_limit", 30),
    }


_INTERVAL_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_interval(interval):
    """Parse an interval like '90', '30m', '1h', '2d' into seconds.

    Returns None if the value can't be parsed.
    """
    if interval is None:
        return None
    if isinstance(interval, (int, float)):
        return int(interval)
    s = str(interval).strip().lower()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    for unit, mult in _INTERVAL_UNITS.items():
        if s.endswith(unit):
            try:
                return int(float(s[:-1]) * mult)
            except ValueError:
                return None
    return None


def get_schedule_config(config):
    """Return schedule settings with defaults."""
    schedule = config.get("schedule", {})
    return {
        "enabled": schedule.get("enabled", False),
        "interval_seconds": parse_interval(schedule.get("interval", "1h")),
    }


def get_notifications_config(config):
    """Return notification settings with defaults (per channel)."""
    notifications = config.get("notifications", {})
    slack = notifications.get("slack", {})
    email = notifications.get("email", {})
    return {
        "slack": {
            "enabled": slack.get("enabled", False),
            "webhook_url": str(slack.get("webhook_url", "") or "").strip(),
        },
        "email": {
            "enabled": email.get("enabled", False),
            "smtp_host": str(email.get("smtp_host", "") or "").strip(),
            "smtp_port": email.get("smtp_port", 587),
            "use_tls": email.get("use_tls", True),
            "username": str(email.get("username", "") or "").strip(),
            "password": str(email.get("password", "") or "").strip(),
            "from": str(email.get("from", "") or "").strip(),
            "to": [str(t).strip() for t in email.get("to", []) if str(t).strip()],
        },
    }


if __name__ == "__main__":
    cfg = load_config()
    print("Config loaded successfully!")
    print(f"  Sources: {[s['name'] for s in get_sources_config(cfg)]}")
    print(f"  Checks: {list(get_checks_config(cfg).keys())}")
    print(f"  Storage: {get_storage_config(cfg)}")
