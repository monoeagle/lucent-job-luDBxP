"""Runtime settings persisted as JSON (singleton-style load/save)."""
import json
import os

import config

_DEFAULTS = {"language": "de", "default_connection": "", "connections": []}


class Settings:
    def __init__(self, data: dict, path: str):
        """Initialize Settings instance.

        Args:
            data: Dictionary of settings.
            path: File path to persist settings.
        """
        self._data = data
        self._path = path

    @classmethod
    def load(cls, path: str = None) -> "Settings":
        """Load settings from JSON file or create with defaults.

        Args:
            path: File path to load from; defaults to config.CONFIG_JSON
                (resolved at call time so tests can redirect it).

        Returns:
            A new Settings instance with loaded or default values.
        """
        path = path or config.CONFIG_JSON
        data = dict(_DEFAULTS)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                data.update(json.load(fh))
        return cls(data, path)

    def get(self, key: str):
        """Get a setting value by key.

        Args:
            key: The setting key.

        Returns:
            The setting value, or default if not found.
        """
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        """Set a setting value by key (call save() to persist)."""
        self._data[key] = value

    def save(self) -> None:
        """Persist settings to JSON file."""
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
