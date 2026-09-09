"""Pytest test suite for Data Watchdog.

Tests cover: config loading, data sources, check registry,
individual checks (volume, schema, nulls, freshness),
notifications, and database operations.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import numpy as np
import pandas as pd
import pytest
import yaml

from config_loader import (
    load_config,
    _expand_env,
    _validate,
    get_checks_config,
    get_sources_config,
    get_storage_config,
    get_notifications_config,
    parse_interval,
)
from sources import CsvSource, PostgresSource, get_source
from checks import CheckRegistry
from checks.volume import VolumeAnomalyCheck
from checks.schema import SchemaChangeCheck
from checks.nulls import NullSpikeCheck
from checks.freshness import FreshnessCheck
from notify import (
    alert_signature,
    build_slack_text,
    build_email,
    send_slack,
    send_email,
)
from monitor import init_db, save_snapshot, load_snapshot, load_history


# ── TestConfigLoader ──────────────────────────────────────────────

class TestConfigLoader:
    """Test config.yaml loading, env expansion, and validation."""

    def test_load_config_returns_dict(self):
        """load_config should return a dict with expected keys."""
        os.environ.setdefault("DB_USER", "watchdog")
        os.environ.setdefault("DB_PASS", "watchdog")
        os.environ.setdefault("DB_HOST", "localhost")
        os.environ.setdefault("DB_PORT", "5432")
        os.environ.setdefault("DB_NAME", "datawatchdog")
        cfg = load_config()
        assert isinstance(cfg, dict)
        assert "data_sources" in cfg
        assert "checks" in cfg

    def test_load_config_file_not_found(self):
        """load_config should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_expand_env_substitutes_variables(self):
        """_expand_env should replace ${VAR} with env values."""
        os.environ["TEST_VAR"] = "hello"
        result = _expand_env("say ${TEST_VAR}")
        assert result == "say hello"
        del os.environ["TEST_VAR"]

    def test_expand_env_missing_optional(self):
        """Optional vars expand to empty string."""
        result = _expand_env("prefix ${NONEXISTENT_VAR_12345}")
        assert result == "prefix "

    def test_expand_env_dict(self):
        """_expand_env should recurse into dicts."""
        os.environ["NESTED_VAL"] = "found"
        result = _expand_env({"key": "${NESTED_VAL}", "other": "static"})
        assert result == {"key": "found", "other": "static"}
        del os.environ["NESTED_VAL"]

    def test_expand_env_list(self):
        """_expand_env should recurse into lists."""
        os.environ["LIST_VAL"] = "item"
        result = _expand_env(["${LIST_VAL}", "static"])
        assert result == ["item", "static"]
        del os.environ["LIST_VAL"]

    def test_validate_missing_data_sources(self):
        """Validation should fail when data_sources is missing."""
        errors = _validate({"checks": {}})
        assert any("data_sources" in e for e in errors)

    def test_validate_missing_checks(self):
        """Validation should fail when checks is missing."""
        errors = _validate({"data_sources": [{"name": "test", "type": "csv", "file": "f.csv"}]})
        assert any("checks" in e for e in errors)

    def test_validate_empty_data_sources(self):
        """Validation should fail for empty data_sources list."""
        errors = _validate({"data_sources": [], "checks": {}})
        assert any("non-empty list" in e for e in errors)

    def test_validate_csv_missing_file(self):
        """Validation should fail for CSV source without file field."""
        errors = _validate({"data_sources": [{"name": "x", "type": "csv"}], "checks": {}})
        assert any("file" in e for e in errors)

    def test_get_checks_config_defaults(self):
        """get_checks_config should fill in defaults."""
        os.environ.setdefault("DB_USER", "watchdog")
        os.environ.setdefault("DB_PASS", "watchdog")
        os.environ.setdefault("DB_HOST", "localhost")
        os.environ.setdefault("DB_PORT", "5432")
        os.environ.setdefault("DB_NAME", "datawatchdog")
        cfg = load_config()
        checks = get_checks_config(cfg)
        assert "volume_anomaly" in checks
        assert checks["volume_anomaly"]["z_threshold"] == 2.0
        assert checks["null_spike"]["threshold_pct"] == 20.0

    def test_get_sources_config(self):
        """get_sources_config returns the data_sources list."""
        os.environ.setdefault("DB_USER", "watchdog")
        os.environ.setdefault("DB_PASS", "watchdog")
        os.environ.setdefault("DB_HOST", "localhost")
        os.environ.setdefault("DB_PORT", "5432")
        os.environ.setdefault("DB_NAME", "datawatchdog")
        cfg = load_config()
        sources = get_sources_config(cfg)
        assert isinstance(sources, list)
        assert len(sources) > 0

    def test_get_storage_config_defaults(self):
        """get_storage_config returns storage with sensible defaults."""
        storage = get_storage_config({})
        assert storage["database"] == "meta.db"
        assert storage["history_limit"] == 30

    def test_get_notifications_config(self):
        """get_notifications_config returns slack and email sections."""
        notifs = get_notifications_config({})
        assert "slack" in notifs
        assert "email" in notifs
        assert notifs["slack"]["enabled"] is False

    def test_parse_interval_seconds(self):
        """parse_interval handles plain seconds."""
        assert parse_interval(60) == 60
        assert parse_interval("90") == 90

    def test_parse_interval_minutes(self):
        """parse_interval handles '30m' format."""
        assert parse_interval("30m") == 1800

    def test_parse_interval_hours(self):
        """parse_interval handles '1h' format."""
        assert parse_interval("1h") == 3600

    def test_parse_interval_days(self):
        """parse_interval handles '2d' format."""
        assert parse_interval("2d") == 172800

    def test_parse_interval_none(self):
        """parse_interval returns None for None input."""
        assert parse_interval(None) is None


# ── TestDataSources ───────────────────────────────────────────────

class TestDataSources:
    """Test data source adapters."""

    def test_csv_source_loads_dataframe(self):
        """CsvSource.load should return a DataFrame."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,name,value\n1,alpha,10\n2,beta,20\n")
            f.flush()
            temp_path = f.name
        try:
            source = CsvSource({"name": "test_csv", "type": "csv", "file": temp_path})
            with patch.object(Path, "__truediv__", return_value=Path(temp_path)):
                df = source.load()
            assert isinstance(df, pd.DataFrame)
            assert len(df) == 2
            assert list(df.columns) == ["id", "name", "value"]
        finally:
            os.unlink(temp_path)

    def test_get_source_csv_factory(self):
        """get_source returns CsvSource for type=csv."""
        src = get_source({"name": "x", "type": "csv", "file": "data.csv"})
        assert isinstance(src, CsvSource)

    def test_get_source_postgres_factory(self):
        """get_source returns PostgresSource for type=postgres."""
        src = get_source({"name": "x", "type": "postgres", "connection_string": "postgresql:///", "table": "t"})
        assert isinstance(src, PostgresSource)

    def test_get_source_unknown_raises(self):
        """get_source raises ValueError for unknown type."""
        with pytest.raises(ValueError, match="Unknown source type"):
            get_source({"name": "x", "type": "redis"})

    def test_base_source_stores_config(self):
        """Source adapters store config and name."""
        src = CsvSource({"name": "my_src", "type": "csv", "file": "f.csv"})
        assert src.name == "my_src"
        assert src.config["type"] == "csv"


# ── TestCheckRegistry ─────────────────────────────────────────────

class TestCheckRegistry:
    """Test check registration and execution."""

    def test_builtin_checks_registered(self):
        """Registry should auto-register all 4 built-in checks."""
        registry = CheckRegistry()
        loaded_names = registry.loaded_checks
        # Not loaded yet, but classes should be available
        assert len(registry._classes) == 4

    def test_load_from_config_enables_checks(self):
        """load_from_config should instantiate enabled checks."""
        registry = CheckRegistry()
        config = {
            "volume_anomaly": {"enabled": True, "z_threshold": 2.0, "min_history": 5},
            "schema_change": {"enabled": True},
            "null_spike": {"enabled": True, "threshold_pct": 20.0},
            "freshness": {"enabled": True, "max_hours": 2},
        }
        registry.load_from_config(config)
        assert len(registry.loaded_checks) == 4

    def test_load_from_config_disables_checks(self):
        """Disabled checks should not be loaded."""
        registry = CheckRegistry()
        config = {
            "volume_anomaly": {"enabled": False},
            "schema_change": {"enabled": True},
            "null_spike": {"enabled": False},
            "freshness": {"enabled": True},
        }
        registry.load_from_config(config)
        assert "volume_anomaly" not in registry.loaded_checks
        assert "null_spike" not in registry.loaded_checks
        assert "schema_change" in registry.loaded_checks

    def test_register_custom_check(self):
        """Custom check class can be registered."""
        registry = CheckRegistry()
        registry.register("custom_check", VolumeAnomalyCheck)
        assert "custom_check" in registry._classes

    def test_run_all_returns_list(self):
        """run_all should return a list of alert dicts."""
        registry = CheckRegistry()
        config = {
            "null_spike": {"enabled": True, "threshold_pct": 20.0},
        }
        registry.load_from_config(config)
        current = {
            "ts": datetime.now().isoformat(),
            "row_count": 100,
            "columns": ["id", "name"],
            "null_counts": {"id": 0, "name": 50},
        }
        alerts = registry.run_all(current, [])
        assert isinstance(alerts, list)
        assert len(alerts) == 1
        assert alerts[0]["type"] == "nulls"


# ── TestChecks ────────────────────────────────────────────────────

class TestChecks:
    """Test individual check implementations."""

    def test_volume_anomaly_no_history(self):
        """Volume check returns empty with insufficient history."""
        check = VolumeAnomalyCheck({"z_threshold": 2.0, "min_history": 5})
        current = {"ts": "2024-01-01 00:00:00", "row_count": 100, "columns": [], "null_counts": {}}
        result = check.run(current, [])
        assert result == []

    def test_volume_anomaly_normal(self):
        """Volume check returns empty for normal data."""
        check = VolumeAnomalyCheck({"z_threshold": 2.0, "min_history": 3})
        history = [{"row_count": 100 + i % 3} for i in range(10)]
        current = {"ts": "2024-01-01", "row_count": 101, "columns": [], "null_counts": {}}
        result = check.run(current, history)
        assert result == []

    def test_volume_anomaly_detected(self):
        """Volume check detects anomalous row count."""
        check = VolumeAnomalyCheck({"z_threshold": 2.0, "min_history": 3})
        history = [{"row_count": 100} for _ in range(10)]
        current = {"ts": "2024-01-01", "row_count": 500, "columns": [], "null_counts": {}}
        result = check.run(current, history)
        assert len(result) == 1
        assert result[0]["type"] == "volume"
        assert result[0]["level"] == "error"

    def test_volume_anomaly_constant_rows_zero_std(self):
        """Volume check with zero std triggers on any deviation."""
        check = VolumeAnomalyCheck({"z_threshold": 2.0, "min_history": 3})
        history = [{"row_count": 100} for _ in range(5)]
        current = {"ts": "2024-01-01", "row_count": 101, "columns": [], "null_counts": {}}
        result = check.run(current, history)
        assert len(result) == 1

    def test_schema_change_no_history(self):
        """Schema check returns empty with no history."""
        check = SchemaChangeCheck({})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["a", "b"], "null_counts": {}}
        result = check.run(current, [])
        assert result == []

    def test_schema_change_no_change(self):
        """Schema check returns empty when columns match."""
        check = SchemaChangeCheck({})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["a", "b"], "null_counts": {}}
        history = [{"columns": ["a", "b"]}]
        result = check.run(current, history)
        assert result == []

    def test_schema_change_column_removed(self):
        """Schema check detects removed columns."""
        check = SchemaChangeCheck({})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["a"], "null_counts": {}}
        history = [{"columns": ["a", "b"]}]
        result = check.run(current, history)
        assert len(result) == 1
        assert result[0]["level"] == "error"
        assert "REMOVED" in result[0]["text"]

    def test_schema_change_column_added(self):
        """Schema check detects added columns."""
        check = SchemaChangeCheck({})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["a", "b", "c"], "null_counts": {}}
        history = [{"columns": ["a", "b"]}]
        result = check.run(current, history)
        assert len(result) == 1
        assert result[0]["level"] == "warning"
        assert "ADDED" in result[0]["text"]

    def test_null_spike_no_rows(self):
        """Null check returns empty when row_count is 0."""
        check = NullSpikeCheck({"threshold_pct": 20.0})
        current = {"ts": "2024-01-01", "row_count": 0, "columns": ["a"], "null_counts": {"a": 0}}
        result = check.run(current, [])
        assert result == []

    def test_null_spike_no_issue(self):
        """Null check returns empty when nulls are below threshold."""
        check = NullSpikeCheck({"threshold_pct": 20.0})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["a"], "null_counts": {"a": 5}}
        result = check.run(current, [])
        assert result == []

    def test_null_spike_detected(self):
        """Null check detects high null percentage."""
        check = NullSpikeCheck({"threshold_pct": 20.0})
        current = {"ts": "2024-01-01", "row_count": 100, "columns": ["amount"], "null_counts": {"amount": 30}}
        result = check.run(current, [])
        assert len(result) == 1
        assert result[0]["type"] == "nulls"
        assert "30.0%" in result[0]["text"]

    def test_freshness_no_history(self):
        """Freshness check returns empty with no history."""
        check = FreshnessCheck({"max_hours": 2})
        current = {"ts": "2024-01-01T00:00:00", "row_count": 100, "columns": [], "null_counts": {}}
        result = check.run(current, [])
        assert result == []

    def test_freshness_data_is_fresh(self):
        """Freshness check returns empty when data is recent."""
        check = FreshnessCheck({"max_hours": 2})
        now = datetime.now()
        current = {"ts": now.isoformat(), "row_count": 100, "columns": [], "null_counts": {}}
        history = [{"ts": (now - timedelta(hours=1)).isoformat()}]
        result = check.run(current, history)
        assert result == []

    def test_freshness_data_is_stale(self):
        """Freshness check detects stale data."""
        check = FreshnessCheck({"max_hours": 2})
        now = datetime.now()
        current = {"ts": now.isoformat(), "row_count": 100, "columns": [], "null_counts": {}}
        history = [{"ts": (now - timedelta(hours=5)).isoformat()}]
        result = check.run(current, history)
        assert len(result) == 1
        assert result[0]["type"] == "freshness"


# ── TestNotifications ─────────────────────────────────────────────

class TestNotifications:
    """Test notification system (Slack, email, dedup)."""

    def test_alert_signature_deterministic(self):
        """Same alerts should produce same signature."""
        alerts = {"src1": [{"type": "volume", "level": "error", "text": "bad"}]}
        sig1 = alert_signature(alerts)
        sig2 = alert_signature(alerts)
        assert sig1 == sig2
        assert isinstance(sig1, str)
        assert len(sig1) == 64  # SHA-256 hex

    def test_alert_signature_different(self):
        """Different alerts should produce different signatures."""
        a1 = {"src": [{"type": "volume", "level": "error", "text": "a"}]}
        a2 = {"src": [{"type": "volume", "level": "error", "text": "b"}]}
        assert alert_signature(a1) != alert_signature(a2)

    def test_build_slack_text_empty(self):
        """build_slack_text returns None when no alerts."""
        assert build_slack_text({}) is None
        assert build_slack_text({"src": []}) is None

    def test_build_slack_text_format(self):
        """build_slack_text returns properly formatted message."""
        alerts = {"orders": [{"type": "volume", "level": "error", "text": "Row count anomaly"}]}
        text = build_slack_text(alerts)
        assert text is not None
        assert "Data Watchdog" in text
        assert "Row count anomaly" in text
        assert "orders" in text

    def test_build_email_empty(self):
        """build_email returns None when no alerts."""
        assert build_email({}) is None

    def test_build_email_format(self):
        """build_email returns (subject, body) tuple."""
        alerts = {"orders": [{"type": "volume", "level": "error", "text": "Row count anomaly"}]}
        result = build_email(alerts)
        assert result is not None
        subject, body = result
        assert "Data Watchdog" in subject
        assert "volume" in body.lower() or "row count" in body.lower()
        assert "Technical details" in body

    @patch("notify.urllib.request.urlopen")
    def test_send_slack_success(self, mock_urlopen):
        """send_slack returns True on success."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"ok"
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        result = send_slack("https://hooks.slack.com/test", "Hello")
        assert result is True

    @patch("notify.urllib.request.urlopen", side_effect=Exception("Connection refused"))
    def test_send_slack_failure(self, mock_urlopen):
        """send_slack returns False on error."""
        result = send_slack("https://hooks.slack.com/test", "Hello")
        assert result is False

    @patch("notify.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp):
        """send_email returns True on success."""
        server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        cfg = {
            "from": "test@example.com",
            "to": ["dest@example.com"],
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "use_tls": True,
            "username": "test@example.com",
            "password": "pass123",
        }
        result = send_email(cfg, "Subject", "Body")
        assert result is True

    def test_send_email_missing_from(self):
        """send_email returns False when from address is missing."""
        result = send_email({"to": ["a@b.com"], "from": ""}, "Sub", "Body")
        assert result is False

    def test_send_email_missing_to(self):
        """send_email returns False when to list is empty."""
        result = send_email({"from": "a@b.com", "to": []}, "Sub", "Body")
        assert result is False


# ── TestDatabase ──────────────────────────────────────────────────

class TestDatabase:
    """Test SQLite database operations."""

    def test_init_db_creates_file(self):
        """init_db should create the database file and table."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with patch("monitor.DB_FILE", Path(db_path)):
                conn = init_db()
                assert conn is not None
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                assert "history" in tables
                conn.close()
        finally:
            os.unlink(db_path)

    def test_save_and_load_snapshot(self):
        """save_snapshot and load_history should round-trip correctly."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with patch("monitor.DB_FILE", Path(db_path)):
                conn = init_db()
                snapshot = {
                    "ts": "2024-01-01 00:00:00",
                    "row_count": 100,
                    "columns": ["a", "b"],
                    "null_counts": {"a": 0, "b": 5},
                }
                save_snapshot(conn, "test_source", snapshot)
                history = load_history(conn, "test_source")
                assert len(history) == 1
                assert history[0]["row_count"] == 100
                assert history[0]["columns"] == ["a", "b"]
                conn.close()
        finally:
            os.unlink(db_path)

    def test_load_history_limit(self):
        """load_history respects the limit parameter."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with patch("monitor.DB_FILE", Path(db_path)):
                conn = init_db()
                for i in range(10):
                    snapshot = {
                        "ts": f"2024-01-{i+1:02d}T00:00:00",
                        "row_count": 100 + i,
                        "columns": ["a"],
                        "null_counts": {"a": 0},
                    }
                    save_snapshot(conn, "src", snapshot)
                history = load_history(conn, "src", limit=3)
                assert len(history) == 3
                assert history[0]["row_count"] == 109
                conn.close()
        finally:
            os.unlink(db_path)

    def test_load_history_wrong_source(self):
        """load_history returns empty for non-existent source."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            with patch("monitor.DB_FILE", Path(db_path)):
                conn = init_db()
                history = load_history(conn, "nonexistent")
                assert history == []
                conn.close()
        finally:
            os.unlink(db_path)


# ── TestIntegration ───────────────────────────────────────────────

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_check_pipeline_no_alerts(self):
        """Full pipeline with clean data produces no alerts."""
        registry = CheckRegistry()
        checks_config = {
            "volume_anomaly": {"enabled": True, "z_threshold": 2.0, "min_history": 5},
            "schema_change": {"enabled": True},
            "null_spike": {"enabled": True, "threshold_pct": 20.0},
            "freshness": {"enabled": True, "max_hours": 24},
        }
        registry.load_from_config(checks_config)

        now = datetime.now()
        history = []
        for i in range(10):
            history.append({
                "ts": (now - timedelta(minutes=5) * (10 - i)).isoformat(),
                "row_count": 100,
                "columns": ["id", "name", "amount"],
                "null_counts": {"id": 0, "name": 0, "amount": 0},
            })

        current = {
            "ts": now.isoformat(),
            "row_count": 100,
            "columns": ["id", "name", "amount"],
            "null_counts": {"id": 0, "name": 0, "amount": 0},
        }

        alerts = registry.run_all(current, history)
        assert alerts == []

    def test_full_check_pipeline_with_alerts(self):
        """Full pipeline with bad data produces alerts."""
        registry = CheckRegistry()
        checks_config = {
            "volume_anomaly": {"enabled": True, "z_threshold": 2.0, "min_history": 3},
            "schema_change": {"enabled": True},
            "null_spike": {"enabled": True, "threshold_pct": 20.0},
            "freshness": {"enabled": True, "max_hours": 2},
        }
        registry.load_from_config(checks_config)

        now = datetime.now()
        history = [
            {"ts": (now - timedelta(minutes=5) * i).isoformat(), "row_count": 100, "columns": ["a", "b"], "null_counts": {"a": 0, "b": 0}}
            for i in range(5, 0, -1)
        ]

        current = {
            "ts": now.isoformat(),
            "row_count": 500,
            "columns": ["a"],
            "null_counts": {"a": 110},
        }

        alerts = registry.run_all(current, history)
        assert len(alerts) >= 2
        alert_types = [a["type"] for a in alerts]
        assert "volume" in alert_types
        assert "schema" in alert_types
        assert "nulls" in alert_types

    def test_registry_skips_unknown_checks(self):
        """Registry should skip unknown check names without crashing."""
        registry = CheckRegistry()
        config = {
            "nonexistent_check": {"enabled": True},
            "null_spike": {"enabled": True, "threshold_pct": 20.0},
        }
        registry.load_from_config(config)
        assert len(registry.loaded_checks) == 1
        assert "null_spike" in registry.loaded_checks

    def test_slack_and_email_message_generation(self):
        """Both notification formats should work together."""
        alerts = {
            "orders": [
                {"type": "volume", "level": "error", "text": "Anomaly detected"},
                {"type": "nulls", "level": "error", "text": "Null spike"},
            ],
        }
        slack_text = build_slack_text(alerts)
        email_result = build_email(alerts)

        assert slack_text is not None
        assert "Anomaly detected" in slack_text
        assert email_result is not None
        subject, body = email_result
        assert "2" in subject
