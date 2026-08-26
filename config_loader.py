import os
import re
from pathlib import Path

from dotenv import load_dotenv
import yaml

CONFIG_FILE = Path(__file__).parent / "config.yaml"

_ENV_PATTERN = re.compile(r"\$\{(\w+)\}")


def _expand_env(value):
    """Replace ${VAR} references with environment variable values."""
    if isinstance(value, str):
        def replacer(match):
            env_val = os.environ.get(match.group(1))
            if env_val is None:
                raise ValueError(f"Environment variable {match.group(1)} is not set")
            return env_val
        return _ENV_PATTERN.sub(replacer, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
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

    data = _expand_env(data)
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


if __name__ == "__main__":
    cfg = load_config()
    print("Config loaded successfully!")
    print(f"  Sources: {[s['name'] for s in get_sources_config(cfg)]}")
    print(f"  Checks: {list(get_checks_config(cfg).keys())}")
    print(f"  Storage: {get_storage_config(cfg)}")
