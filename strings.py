"""UI text internationalization (DE/EN)."""
_STRINGS = {
    "app_title":   {"de": "Lucent DB Explorer", "en": "Lucent DB Explorer"},
    "btn_load":    {"de": "Schema laden",        "en": "Load schema"},
    "btn_build":   {"de": "Join-Pfad bauen",     "en": "Build join path"},
    "lbl_start":   {"de": "Start",               "en": "Start"},
    "lbl_target":  {"de": "Ziel",                "en": "Target"},
    "err_no_path": {"de": "Keine Join-Verbindung gefunden",
                    "en": "No join path found"},
}
_lang = "de"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in ("de", "en") else "de"


def t(key: str) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return f"[{key}]"
    return entry.get(_lang, entry.get("de", f"[{key}]"))
