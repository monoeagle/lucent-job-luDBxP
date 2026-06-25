"""Loader contract: every schema source implements load() -> Schema."""
from abc import ABC, abstractmethod
from core.model import Schema


class SchemaLoader(ABC):
    @abstractmethod
    def load(self) -> Schema:
        """Read a schema source and return the domain Schema."""
