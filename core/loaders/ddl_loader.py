"""Stub: SQL DDL file parser (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class DdlLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("SQL DDL parser is planned for a later version.")
