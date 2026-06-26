<#
  Lucent DB Explorer launcher (Windows / PowerShell).
  Run with no argument for an interactive menu; pass a flag for direct,
  non-interactive actions. Mirrors run.sh.

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

# Offline wheelhouse (bundled Windows wheels). When present, setup runs without
# internet. The compiled wheels are built for CPython 3.12 (win_amd64).
$Wheels = Join-Path $PSScriptRoot 'wheels'

function Find-Python {
    # With the offline wheelhouse, require Python 3.12 to match the cp312 wheels;
    # otherwise prefer the newest available.
    $versions = if (Test-Path $Wheels) { @('3.12') } else { @('3.13', '3.12', '3.11', '3.10') }
    foreach ($v in $versions) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py "-$v" --version *> $null
            if ($LASTEXITCODE -eq 0) { return @('py', "-$v") }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @('python') }
    if (Test-Path $Wheels) {
        throw 'Python 3.12 (64-bit) wird fuer das Offline-Setup benoetigt (passend zu wheels\).'
    }
    throw 'Kein Python gefunden (py oder python).'
}

function Setup-Venv {
    if (-not (Test-Path $VenvPy)) {
        $py = Find-Python
        & $py[0] $py[1..($py.Count - 1)] -m venv $Venv
    }
    $newHash = (Get-FileHash 'requirements.txt' -Algorithm MD5).Hash
    $oldHash = if (Test-Path $Stamp) { Get-Content $Stamp -Raw } else { '' }
    if ($newHash -ne $oldHash.Trim()) {
        if (Test-Path $Wheels) {
            Write-Host '  Offline-Setup: installiere aus wheels\ (kein Internet noetig)...'
            & $VenvPip install --no-index --find-links $Wheels -r requirements.txt
        } else {
            & $VenvPip install -r requirements.txt
        }
        Set-Content -Path $Stamp -Value $newHash -NoNewline
    }
}

# --- Actions (shared by the flags and the menu) ---------------------------
function Do-Start      { Setup-Venv; & $VenvPy app.py }
function Do-SetupVenv  { Setup-Venv }
function Do-SkipSetup  { & $VenvPy app.py }
function Do-Clean      {
    if (Test-Path $Venv)  { Remove-Item $Venv -Recurse -Force }
    if (Test-Path $Stamp) { Remove-Item $Stamp -Force }
    Setup-Venv
}
function Do-Version    { & $VenvPy -c 'import config; print(config.APP_VERSION)' }
function Do-Tests {
    Setup-Venv
    if (Test-Path $Wheels) {
        & $VenvPip install -q --no-index --find-links $Wheels -r requirements-dev.txt
    } else {
        & $VenvPip install -q -r requirements-dev.txt
    }
    & $VenvPy -m pytest
}
function Do-DemoDb {
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
        switch ($choice) {
            '1' { Do-Start }
            '2' { Do-SetupVenv; Write-Host '  Umgebung bereit.' }
            '3' { Do-SkipSetup }
            '4' { Do-Clean; Write-Host '  Umgebung neu aufgebaut.' }
            '5' { Do-Tests }
            '6' { Do-DemoDb }
            '7' { Do-Version }
            '0' { return }
            default { Write-Host "  Ungueltige Auswahl: $choice" }
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
