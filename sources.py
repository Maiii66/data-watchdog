from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class BaseSource(ABC):
    """Abstract base for data source adapters.

    Subclasses implement load() which returns a pandas DataFrame.
    The monitor builds the snapshot dict from this DataFrame.
    """

    def __init__(self, config):
        self.config = config
        self.name = config.get("name", "unknown")

    @abstractmethod
    def load(self):
        """Load data and return a pandas DataFrame."""
        ...


class CsvSource(BaseSource):
    """Load data from a local CSV file."""

    def load(self):
        path = Path(__file__).parent / self.config["file"]
        return pd.read_csv(path)


class PostgresSource(BaseSource):
    """Load data from a PostgreSQL table."""

    def load(self):
        from sqlalchemy import create_engine

        conn_str = self.config["connection_string"]
        table = self.config["table"]
        engine = create_engine(conn_str)
        return pd.read_sql_table(table, engine)


_TYPE_MAP = {
    "csv": CsvSource,
    "postgres": PostgresSource,
}


def get_source(config):
    """Factory: return the right source adapter based on config type."""
    source_type = config.get("type", "csv")
    cls = _TYPE_MAP.get(source_type)
    if cls is None:
        raise ValueError(f"Unknown source type: {source_type!r}. Supported: {list(_TYPE_MAP)}")
    return cls(config)
