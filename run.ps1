<#
  Lucent DB Explorer launcher (Windows / PowerShell).
  Run with no argument for an interactive menu; pass a flag for direct,
  non-interactive actions. Mirrors run.sh.

  AP-15: abbruchsicher + idempotent. Jeder Schritt prueft seine Vorbedingungen
  (Python, venv-Integritaet, Paket-Vollstaendigkeit, Port) und zieht Fehlendes
  nach, sodass ein zuvor abgebrochener Lauf (halbes venv, halber pip-Install)
  beim naechsten Mal sauber zu Ende gefuehrt wird. Jeder Schritt meldet Status.

  Usage:
    .\run.ps1                 # interactive menu
    .\run.ps1 -Action start | setup-venv | skip-setup | clean | tests | demo-db | version
#>
param(
    [ValidateSet('menu', 'start', 'setup-venv', 'skip-setup', 'clean', 'tests', 'demo-db', 'version')]
    [string]$Action = 'menu'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

# Absolute paths: PowerShell's & operator does not resolve a relative program
# path against the working directory, so a bare "venv\Scripts\python.exe" would
# fail with "not recognized" even on Windows. Anchor on $PSScriptRoot.
$Venv    = Join-Path $PSScriptRoot 'venv'
$Stamp   = Join-Path $PSScriptRoot '.req_stamp'
$VenvPy  = Join-Path $Venv 'Scripts\python.exe'
$VenvPip = Join-Path $Venv 'Scripts\pip.exe'
$Port    = 5057

# Offline wheelhouse (bundled Windows wheels). When present, setup runs without
# internet. The compiled wheels are built for CPython 3.14 (win_amd64).
$Wheels = Join-Path $PSScriptRoot 'wheels'

# --- Status helpers (AP-15: durchgaengiger Statusausgabebereich) -----------
# ASCII-Marker, damit die Windows-Konsole (cp1252) nichts verschluckt.
function _ok   ($m) { Write-Host "  [ OK ] $m"  -ForegroundColor Green }
function _warn ($m) { Write-Host "  [WARN] $m"  -ForegroundColor Yellow }
function _info ($m) { Write-Host "  [ .. ] $m"  -ForegroundColor Cyan }
function _hdr  ($m) { Write-Host ""; Write-Host "=== $m ===" -ForegroundColor White }
function _fail ($m) { Write-Host "  [FAIL] $m"  -ForegroundColor Red; throw $m }

function Find-Python {
    # With the offline wheelhouse, require Python 3.14 to match the cp314 wheels;
    # otherwise prefer the newest available.
    $versions = if (Test-Path $Wheels) { @('3.14') } else { @('3.14', '3.13', '3.12', '3.11', '3.10') }
    foreach ($v in $versions) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py "-$v" --version *> $null
            if ($LASTEXITCODE -eq 0) { return @('py', "-$v") }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @('python') }
    if (Test-Path $Wheels) {
        throw 'Python 3.14 (64-bit) wird fuer das Offline-Setup benoetigt (passend zu wheels\).'
    }
    throw 'Kein Python gefunden (py oder python).'
}

# AP-15: venv-Integritaet pruefen, nicht nur Existenz. Ein mittendrin
# abgebrochenes `python -m venv` hinterlaesst ggf. ein Verzeichnis ohne
# funktionsfaehigen Interpreter — das wuerde ein blosses Test-Path uebersehen.
function Test-VenvHealthy {
    if (-not (Test-Path $VenvPy)) { return $false }
    & $VenvPy -c 'import sys' *> $null 2>&1
    return ($LASTEXITCODE -eq 0)
}

# AP-15: sind alle Laufzeit-Pakete installiert und konsistent? `pip check`
# meldet fehlende/inkompatible Abhaengigkeiten — faengt einen abgebrochenen
# pip-Install, bei dem der Stamp noch nicht geschrieben wurde.
function Test-RequirementsInstalled {
    if (-not (Test-Path $VenvPip)) { return $false }
    & $VenvPip check *> $null 2>&1
    return ($LASTEXITCODE -eq 0)
}

function Test-PortFree ($p) {
    try {
        $listen = Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction Stop
        return (-not $listen)
    } catch {
        # Kein Listener gefunden (oder Cmdlet nicht verfuegbar) -> Port frei annehmen.
        return $true
    }
}

# AP-15 / NO-CDN: Installation AUSSCHLIESSLICH aus lokalen Quellen (wheels\),
# niemals aus dem Netz. Vor jeder Installation wird per --dry-run geprueft, ob
# alle benoetigten Wheels lokal vorliegen (--no-index unterbindet jeden
# PyPI-Zugriff). Fehlt das Wheelhouse oder ein Wheel, wird mit Fehlermeldung
# UND Protokoll (welche Pakete fehlen) ausgestiegen — es erfolgt KEINE
# (Teil-)Installation und KEIN Online-Nachladen.
function Install-Requirements ($reqFile) {
    if (-not (Test-Path $Wheels)) {
        _fail "Wheelhouse 'wheels\' fehlt — KEINE Installation, kein Online-Nachladen."
    }
    _info "Pruefe lokale Wheels fuer $reqFile (--dry-run, kein Netz)..."
    $probe = & $VenvPip install --no-index --find-links $Wheels --dry-run -r $reqFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ''
        _warn "Es fehlen lokale Wheels — Protokoll (pip --no-index):"
        $probe | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkYellow }
        Write-Host ''
        _fail "Offline-Setup abgebrochen ($reqFile): nicht alle Wheels lokal vorhanden. KEINE Installation."
    }
    _ok "alle benoetigten Wheels lokal vorhanden"
    _info "Offline-Install strikt aus wheels\ (--no-index, kein Netz): $reqFile"
    & $VenvPip install --no-index --find-links $Wheels -r $reqFile
    if ($LASTEXITCODE -ne 0) { _fail "Offline-Install aus wheels\ fehlgeschlagen ($reqFile)." }
}

# AP-15: idempotenter, selbstheilender Setup-Schritt. Prueft jede Vorbedingung
# und zieht nur das Fehlende nach. Der Stamp wird erst NACH erfolgreichem
# Install + Verifikation geschrieben (atomar): bricht der Install ab, bleibt
# kein/der alte Stamp, sodass der naechste Lauf ihn wiederholt.
function Ensure-Venv {
    _hdr "Umgebung pruefen"

    if (Test-VenvHealthy) {
        _ok "venv funktionsfaehig"
    } else {
        if (Test-Path $Venv) {
            _warn "venv unvollstaendig/kaputt — wird neu aufgebaut"
            Remove-Item $Venv -Recurse -Force
        }
        $py = Find-Python
        _info "venv anlegen ($($py -join ' '))..."
        & $py[0] $py[1..($py.Count - 1)] -m venv $Venv
        if (-not (Test-VenvHealthy)) { _fail "venv-Erstellung fehlgeschlagen." }
        _ok "venv angelegt"
    }

    $newHash = (Get-FileHash 'requirements.txt' -Algorithm MD5).Hash
    $oldHash = if (Test-Path $Stamp) { (Get-Content $Stamp -Raw).Trim() } else { '' }
    $needInstall = $false
    if ($newHash -ne $oldHash) {
        _info "requirements.txt geaendert (oder Erstinstallation)"
        $needInstall = $true
    } elseif (-not (Test-RequirementsInstalled)) {
        _warn "Pakete unvollstaendig (pip check) — Reparatur-Install"
        $needInstall = $true
    } else {
        _ok "Laufzeit-Pakete vollstaendig"
    }

    if ($needInstall) {
        if (Test-Path $Stamp) { Remove-Item $Stamp -Force }   # erst nach Erfolg wieder schreiben
        Install-Requirements 'requirements.txt'
        if (-not (Test-RequirementsInstalled)) { _fail "Pakete nach Install weiterhin inkonsistent (pip check)." }
        Set-Content -Path $Stamp -Value $newHash -NoNewline
        _ok "Laufzeit-Pakete installiert"
    }
}

function Start-App {
    _hdr "App starten"
    if (-not (Test-VenvHealthy)) { _fail "venv nicht funktionsfaehig — bitte zuerst 'setup-venv'." }
    if (-not (Test-PortFree $Port)) {
        _warn "Port $Port ist bereits belegt — laeuft schon eine Instanz? Start abgebrochen."
        return
    }
    _info "Starte http://127.0.0.1:$Port/  (Strg+C zum Beenden)"
    & $VenvPy app.py
    $code = $LASTEXITCODE
    if ($code -and $code -ne 0) { _warn "App beendet mit Exit-Code $code" }
}

# --- Actions (shared by the flags and the menu) ---------------------------
function Do-Start      { Ensure-Venv; Start-App }
function Do-SetupVenv  { Ensure-Venv; _ok "Umgebung bereit." }
function Do-SkipSetup {
    if (-not (Test-VenvHealthy)) {
        _fail "venv fehlt/kaputt — bitte zuerst '.\run.ps1 -Action setup-venv'."
    }
    Start-App
}
function Do-Clean {
    _hdr "Umgebung neu aufbauen"
    if (Test-Path $Venv)  { _info "venv entfernen..."; Remove-Item $Venv -Recurse -Force }
    if (Test-Path $Stamp) { Remove-Item $Stamp -Force }
    Ensure-Venv
    _ok "Umgebung neu aufgebaut."
}
function Do-Version {
    if (-not (Test-VenvHealthy)) { _fail "venv nicht funktionsfaehig — bitte zuerst 'setup-venv'." }
    & $VenvPy -c 'import config; print(config.APP_VERSION)'
}
function Do-Tests {
    Ensure-Venv
    _hdr "Tests"
    & $VenvPy -c 'import pytest' *> $null 2>&1
    if ($LASTEXITCODE -ne 0) { Install-Requirements 'requirements-dev.txt' }
    else { _ok "Test-Abhaengigkeiten vorhanden" }
    & $VenvPy -m pytest
}
function Do-DemoDb {
    _hdr "Demo-DB erzeugen"
    $py = Find-Python
    & $py[0] $py[1..($py.Count - 1)] sample_data/build_demo_db.py
}

# --- Interactive menu -----------------------------------------------------
function Show-Menu {
    Write-Host ''
    Write-Host '  Lucent DB Explorer'
    Write-Host '  =================='
    Write-Host '  1) App starten (Setup, falls noetig)'
    Write-Host '  2) Nur Umgebung einrichten (venv + pip)'
    Write-Host '  3) App schnell starten (ohne Setup-Check)'
    Write-Host '  4) Umgebung neu aufbauen (clean)'
    Write-Host '  5) Tests ausfuehren'
    Write-Host '  6) Demo-DB neu erzeugen'
    Write-Host '  7) Version anzeigen'
    Write-Host '  0) Beenden'
    Write-Host ''
}

function Menu-Loop {
    while ($true) {
        Show-Menu
        $choice = Read-Host '  Auswahl'
        # AP-15: ein fehlgeschlagener Schritt (_fail) darf das Menue nicht beenden.
        try {
            switch ($choice) {
                '1' { Do-Start }
                '2' { Do-SetupVenv }
                '3' { Do-SkipSetup }
                '4' { Do-Clean }
                '5' { Do-Tests }
                '6' { Do-DemoDb }
                '7' { Do-Version }
                '0' { return }
                default { Write-Host "  Ungueltige Auswahl: $choice" }
            }
        } catch {
            _warn "Abgebrochen: $($_.Exception.Message)"
        }
    }
}

# --- Dispatch -------------------------------------------------------------
switch ($Action) {
    'menu'       { Menu-Loop }
    'start'      { Do-Start }
    'setup-venv' { Do-SetupVenv }
    'skip-setup' { Do-SkipSetup }
    'clean'      { Do-Clean }
    'tests'      { Do-Tests }
    'demo-db'    { Do-DemoDb }
    'version'    { Do-Version }
}
