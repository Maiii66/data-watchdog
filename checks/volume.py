import numpy as np

from checks.base import BaseCheck


class VolumeAnomalyCheck(BaseCheck):
    name = "volume_anomaly"
    alert_type = "volume"

    def run(self, current, history):
        z_threshold = self.config.get("z_threshold", 2.0)
        min_history = self.config.get("min_history", 5)

        if len(history) < min_history:
            return []

        counts = np.array([s["row_count"] for s in history])
        mean = float(counts.mean())
        std = float(counts.std(ddof=0))

        if std == 0:
            if current["row_count"] != mean:
                return [{
                    "type": self.alert_type,
                    "level": "error",
                    "text": f"Row count anomaly! Today: {current['row_count']}, avg: {mean:.0f}, z-score: inf",
                }]
            return []

        z = (current["row_count"] - mean) / std
        if abs(z) > z_threshold:
            return [{
                "type": self.alert_type,
                "level": "error",
                "text": f"Row count anomaly! Today: {current['row_count']}, avg: {mean:.0f}, z-score: {z:.1f}",
            }]
        return []
