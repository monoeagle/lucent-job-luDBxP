import pytest
from core.schema_loader import SchemaLoader
from core.loaders.manual_loader import ManualLoader
from core.loaders.schemaspy_loader import SchemaSpyLoader
from core.loaders.ddl_loader import DdlLoader


def test_cannot_instantiate_abstract_loader():
    with pytest.raises(TypeError):
        SchemaLoader()  # abstract


@pytest.mark.parametrize("cls", [ManualLoader, SchemaSpyLoader, DdlLoader])
def test_stub_loaders_raise_not_implemented(cls):
    loader = cls()
    with pytest.raises(NotImplementedError):
        loader.load()
