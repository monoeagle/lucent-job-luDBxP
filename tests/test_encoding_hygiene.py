"""AP-72.S1 - Encoding-Hygiene-Guard.

Verhindert, dass Mojibake (doppelt kodierte UTF-8-Bytes), ein UTF-8-BOM oder
ungueltiges UTF-8 in getrackte Code-Dateien gelangt. Reiner Test, kein
Produktionscode. Markdown/Doku bewusst ausgenommen (duerfen solche Muster als
Beispiel legitim tragen); generierte Site-/Build-Artefakte ausgeschlossen.

Diese Datei ist bewusst reines ASCII: alle Nicht-ASCII-Zeichen werden aus
chr(0x..)-Codepoints gebaut, damit der Guard sich nicht selbst flaggt.
"""
import re
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CODE_SUFFIXES = {".py", ".js", ".html", ".css", ".sh", ".ps1"}
_EXCLUDED_PREFIXES = ("luDBxP-docs/site/", "build/")
_BOM = b"\xef\xbb\xbf"

# Doppelkodierungs-Signatur: ein Fuehrungsbyte-Zeichen aus dem Mojibake-Alphabet
# (UTF-8-Leadbytes 0xC2/0xC3/0xE2 fehl-dekodiert) direkt gefolgt von einem
# Zeichen, das der Fehl-Decoder aus einem UTF-8-Folgebyte (0x80-0xBF) macht.
# _CONT deckt BEIDE haeufigen Korruptionspfade ab: Latin-1 (0x80-0xBF -> gleiche
# Codepoints, z.B. 0xC3+0xBC = ue-Umlaut-Mojibake) UND Windows-1252 (0x80-0x9F ->
# Smartquotes/Dashes/dagger, z.B. der Pfeil U+2192 wird zu 'a-circ + dagger').
# Echte Umlaute (ue=0xFC) und echte Mehrbyte-Zeichen (Pfeil=U+2192) matchen nicht
# -> sie dekodieren als EIN Codepoint. Alles aus chr()/Codepoints gebaut, damit
# diese Datei reines ASCII bleibt und sich nicht selbst flaggt.
_LEAD = "".join(chr(b) for b in (0xC2, 0xC3, 0xE2))
_TRAIL = bytes(range(0x80, 0xC0))
_CONT = "".join(sorted(set(_TRAIL.decode("latin-1"))
                       | set(_TRAIL.decode("cp1252", errors="ignore"))))
_MOJIBAKE_RE = re.compile("[" + _LEAD + "][" + _CONT + "]")


def _tracked_code_files():
    # -z: NUL-separiert und OHNE Pfad-Quoting -> Nicht-ASCII-Dateinamen kommen
    # roh durch (sonst wuerde git sie als "caf\303\251.py" quoten und der Filter
    # sie still ueberspringen).
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files", "-z"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        pytest.skip("kein git-Repo (git ls-files fehlgeschlagen)")
    files = []
    for rel in out.stdout.split("\0"):
        if not rel or Path(rel).suffix not in _CODE_SUFFIXES:
            continue
        if rel.startswith(_EXCLUDED_PREFIXES):
            continue
        p = _REPO_ROOT / rel
        if p.is_file():
            files.append((rel, p))
    return files


def _violations(rel, raw, allow_bom=False):
    """Alle Encoding-Verstoesse einer Datei als (rel, zeile, art)-Tupel.

    allow_bom: .ps1-Skripte duerfen ein UTF-8-BOM tragen - PowerShell 5.1 liest
    BOM-lose Dateien sonst als ANSI (Windows-1252) und verstuemmelt Nicht-ASCII.
    Das BOM auf run.ps1 ist ein bewusster Deploy-Fix (Roadmap v0.11.1
    "PowerShell 5.1: ASCII+BOM"), darum dort erlaubt.
    """
    out = []
    if raw.startswith(_BOM):
        if not allow_bom:
            out.append((rel, 1, "UTF-8-BOM"))
        raw = raw[len(_BOM):]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        out.append((rel, 1, "kein gueltiges UTF-8: " + str(e)))
        return out
    for i, line in enumerate(text.splitlines(), 1):
        m = _MOJIBAKE_RE.search(line)
        if m:
            out.append((rel, i, "Mojibake " + repr(m.group())))
    return out


def test_guard_detects_injected_mojibake(tmp_path):
    """Beweist, dass der Checker greift (nicht tautologisch gruen)."""
    # 0xC3 0xA9 == doppelt kodiertes e-accent (Mojibake-Sequenz).
    mojibake = "caf" + chr(0xC3) + chr(0xA9)
    bad = tmp_path / "bad.py"
    bad.write_bytes(("x = '" + mojibake + "'\n").encode("utf-8"))
    v = _violations("bad.py", bad.read_bytes())
    assert v and "Mojibake" in v[0][2]

    # CP1252-Pfad: der Pfeil U+2192 (UTF-8 E2 86 92), per cp1252 fehl-dekodiert,
    # ergibt 'a-circ + dagger + quote' - Byte 0x86 -> U+2020, ausserhalb 0x80-0xBF,
    # wird also NUR mit der CP1252-Erweiterung von _CONT erkannt (Review-Fund).
    arrow_mojibake = chr(0x2192).encode("utf-8").decode("cp1252")
    arrow = tmp_path / "arrow.py"
    arrow.write_bytes(("y = '" + arrow_mojibake + "'\n").encode("utf-8"))
    assert _violations("arrow.py", arrow.read_bytes()), "CP1252-Pfeil-Mojibake muss erkannt werden"

    bom = tmp_path / "bom.py"
    bom.write_bytes(_BOM + b"x = 1\n")
    assert any("BOM" in art for _, _, art in _violations("bom.py", bom.read_bytes()))

    # Echte Umlaute (u-umlaut 0xFC, sz 0xDF) sind KEIN Verstoss:
    real = "gr" + chr(0xFC) + chr(0xDF)
    good = tmp_path / "good.py"
    good.write_bytes(("x = '" + real + "'\n").encode("utf-8"))
    assert _violations("good.py", good.read_bytes()) == []


def test_source_files_are_clean_utf8():
    files = _tracked_code_files()
    assert files, "keine Code-Dateien gefunden (unerwartet)"
    bad = []
    for rel, p in files:
        bad.extend(_violations(rel, p.read_bytes(), allow_bom=rel.endswith(".ps1")))
    assert not bad, "Encoding-Verstoesse:\n" + "\n".join(
        "  {}:{}: {}".format(rel, ln, art) for rel, ln, art in bad)
