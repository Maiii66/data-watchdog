from checks.volume import VolumeAnomalyCheck
from checks.schema import SchemaChangeCheck
from checks.nulls import NullSpikeCheck
from checks.freshness import FreshnessCheck

_BUILTIN = {
    "volume_anomaly": VolumeAnomalyCheck,
    "schema_change": SchemaChangeCheck,
    "null_spike": NullSpikeCheck,
    "freshness": FreshnessCheck,
}


class CheckRegistry:
    """Discovers, instantiates, and runs data quality checks.

    Built-in checks are registered automatically. Custom checks can be
    added via register() before calling load_from_config().
    """

    def __init__(self):
        self._classes = dict(_BUILTIN)
        self._instances = []

    def register(self, name, check_class):
        """Register a custom check class by name."""
        self._classes[name] = check_class

    def load_from_config(self, checks_config):
        """Instantiate enabled checks from the config dict.

        Args:
            checks_config: dict like {"volume_anomaly": {"enabled": true, "z_threshold": 2.0}, ...}
        """
        self._instances = []
        for name, cfg in checks_config.items():
            if not cfg.get("enabled", True):
                continue
            cls = self._classes.get(name)
            if cls is None:
                print(f"Warning: unknown check '{name}', skipping")
                continue
            self._instances.append(cls(cfg))

    def run_all(self, current, history):
        """Run all loaded checks and return combined alerts.

        Args:
            current: current snapshot dict
            history: list of previous snapshot dicts

        Returns:
            list of alert dicts
        """
        alerts = []
        for check in self._instances:
            try:
                result = check.run(current, history)
                if result is None:
                    result = []
                elif not isinstance(result, list):
                    result = [result]
                alerts.extend(result)
            except Exception as exc:
                alerts.append({
                    "type": check.alert_type,
                    "level": "error",
                    "text": f"Check '{check.name}' failed: {exc}",
                })
        return alerts

    @property
    def loaded_checks(self):
        return [c.name for c in self._instances]
