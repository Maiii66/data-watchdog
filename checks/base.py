from abc import ABC, abstractmethod


class BaseCheck(ABC):
    """Base class for all data quality checks.

    Subclasses must implement `run()` which returns a list of alert dicts.
    Each alert dict has: {"type": str, "level": str, "text": str}
    """

    name: str = "base"
    alert_type: str = "base"

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def run(self, current, history):
        """Run the check against current snapshot and history.

        Args:
            current: dict with ts, row_count, columns, null_counts
            history: list of previous snapshot dicts (newest first)

        Returns:
            list of alert dicts, empty if no issues
        """
        return []
