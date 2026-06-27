"""Per-user data locations and dynamic port selection (AP-31 core slice).

Pure stdlib module — no Flask, no `config` import (the app slug is passed in),
so it stays free of the web layer and import cycles. Resolves OS-standard
per-user paths for config + logs, picks a free TCP port, and migrates a legacy
app-directory config.json once.
"""
import os
import shutil
import socket


def _app_base(app_slug, *, kind):
    """OS base directory for this app's per-user data.

    kind is "config" or "state" (state = logs). On Windows both map to
    %LOCALAPPDATA%\\<slug>; on POSIX they follow the XDG base-dir spec.
    """
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(root, app_slug)
    if kind == "config":
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config")
    else:
        root = os.environ.get("XDG_STATE_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "state")
    return os.path.join(root, app_slug)


def user_config_dir(app_slug):
    """Per-user config directory (created). LUCENT_CONFIG_DIR overrides."""
    d = os.environ.get("LUCENT_CONFIG_DIR") or _app_base(app_slug, kind="config")
    os.makedirs(d, exist_ok=True)
    return d


def user_config_file(app_slug, filename="config.json"):
    """Full path to the per-user config file (directory created)."""
    return os.path.join(user_config_dir(app_slug), filename)


def user_log_dir(app_slug):
    """Per-user log directory (created). LUCENT_LOG_DIR overrides."""
    d = os.environ.get("LUCENT_LOG_DIR")
    if not d:
        base = _app_base(app_slug, kind="state")
        d = os.path.join(base, "Logs" if os.name == "nt" else "logs")
    os.makedirs(d, exist_ok=True)
    return d
