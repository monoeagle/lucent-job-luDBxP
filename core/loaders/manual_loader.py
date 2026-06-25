"""Stub: manual JSON/YAML schema definition (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class ManualLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("Manual JSON/YAML loader is planned for a later version.")
