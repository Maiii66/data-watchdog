from datetime import datetime, timedelta

from checks.base import BaseCheck


class FreshnessCheck(BaseCheck):
    name = "freshness"
    alert_type = "freshness"

    def run(self, current, history):
        max_hours = self.config.get("max_hours", 2)

        if not history:
            return []

        try:
            previous_ts = datetime.fromisoformat(history[0]["ts"])
            current_ts = datetime.fromisoformat(current["ts"])
        except ValueError:
            return []

        if current_ts - previous_ts > timedelta(hours=max_hours):
            return [{
                "type": self.alert_type,
                "level": "warning",
                "text": "Data may be stale: last snapshot is more than 2 hours old.",
            }]
        return []
