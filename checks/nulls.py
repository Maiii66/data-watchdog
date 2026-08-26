from checks.base import BaseCheck


class NullSpikeCheck(BaseCheck):
    name = "null_spike"
    alert_type = "nulls"

    def run(self, current, history):
        threshold = self.config.get("threshold_pct", 20.0)
        row_count = current["row_count"]

        if row_count == 0:
            return []

        alerts = []
        for column, null_count in current["null_counts"].items():
            pct = null_count / row_count * 100
            if pct > threshold:
                alerts.append({
                    "type": self.alert_type,
                    "level": "error",
                    "text": f"NULL spike in '{column}': {pct:.1f}% of rows are null!",
                })
        return alerts
