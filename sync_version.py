"""Version sync: bump config.APP_VERSION and lucent-hub.yml in lockstep.

Usage: python sync_version.py --patch | --minor | --major | --set X.Y.Z
NEVER edit config.py APP_VERSION manually.
"""
import re
import sys

import config

_VER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def bump(current: str, kind: str, explicit: str = "") -> str:
    """Bump version string according to semver rules.

    Args:
        current: Current version string (e.g., "0.1.0").
        kind: Bump kind ("patch", "minor", "major", or "set").
        explicit: New version for "set" kind; must match X.Y.Z format.

    Returns:
        The new version string.

    Raises:
        ValueError: If kind is unknown or explicit version does not match X.Y.Z format.
    """
    if kind == "set":
        if not _VER_RE.match(explicit):
            raise ValueError(f"Invalid version: {explicit}")
        return explicit
    major, minor, patch = (int(x) for x in current.split("."))
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "major":
        return f"{major + 1}.0.0"
    raise ValueError(f"Unknown bump kind: {kind}")


def _write(new_version: str) -> None:
    """Write new version to config.py and lucent-hub.yml.

    Args:
        new_version: The new version string to persist.
    """
    import os
    cfg = os.path.join(config.BASE_DIR, "config.py")
    with open(cfg, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{new_version}"', text)
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write(text)
    hub = os.path.join(config.BASE_DIR, "lucent-hub.yml")
    if os.path.exists(hub):
        with open(hub, encoding="utf-8") as fh:
            htext = fh.read()
        htext = re.sub(r'version: "[^"]+"', f'version: "{new_version}"', htext)
        with open(hub, "w", encoding="utf-8") as fh:
            fh.write(htext)


def main(argv: list[str]) -> None:
    """CLI entry point for version bumping.

    Args:
        argv: Command-line arguments (argv[0] is script name).
    """
    flag = argv[1] if len(argv) > 1 else ""
    mapping = {"--patch": "patch", "--minor": "minor", "--major": "major"}
    if flag in mapping:
        new = bump(config.APP_VERSION, mapping[flag])
    elif flag == "--set" and len(argv) > 2:
        new = bump(config.APP_VERSION, "set", argv[2])
    else:
        print("Usage: sync_version.py --patch|--minor|--major|--set X.Y.Z")
        return
    _write(new)
    print(f"Version: {config.APP_VERSION} -> {new}")


if __name__ == "__main__":
    main(sys.argv)
