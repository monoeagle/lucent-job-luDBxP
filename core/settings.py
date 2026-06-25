"""Runtime settings persisted as JSON (singleton-style load/save)."""
import json
import os

import config

_DEFAULTS = {"language": "de", "default_connection": ""}


class Settings:
    def __init__(self, data: dict, path: str):
        self._data = data
        self._path = path

    @classmethod
    def load(cls, path: str = config.CONFIG_JSON) -> "Settings":
        data = dict(_DEFAULTS)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data.update(json.load(fh))
        return cls(data, path)

    def get(self, key: str):
        return self._data.get(key, _DEFAULTS.get(key))

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
