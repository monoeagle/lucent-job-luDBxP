"""Stub: SchemaSpy metadata import (later iteration)."""
from core.schema_loader import SchemaLoader
from core.model import Schema


class SchemaSpyLoader(SchemaLoader):
    def load(self) -> Schema:
        raise NotImplementedError("SchemaSpy import is planned for a later version.")
