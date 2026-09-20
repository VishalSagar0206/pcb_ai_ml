<#
.SYNOPSIS
  One-command startup for PCB DRC Intelligence on Windows, without Docker.

.DESCRIPTION
  For anyone whose machine can't run Docker: this sets up a Python virtual
  environment + backend dependencies, installs frontend dependencies,
  ensures a .env file exists (guiding first-time Gemini API key setup),
  then starts both the backend (FastAPI/uvicorn on http://127.0.0.1:8931)
  and frontend (Vite dev server on http://localhost:5173) each in their own
  visible console window, and opens the app in the default browser.

  Safe to re-run: it skips steps that are already done (dependency install,
  .env creation) and won't start a second copy of a server that's already
  running -- just double-click start.bat again any time.

  Normally launched via ..\..\start.bat (double-click), not run directly.
#>

$ErrorActionPreference = 'Stop'

# --- Resolve repo root (this script lives in <root>\scripts\windows) ---
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root

$BackendPort = 8931
$FrontendPort = 5173
$BackendUrl = "http://127.0.0.1:$BackendPort"
$FrontendUrl = "http://localhost:$FrontendPort"

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Info2($msg) { Write-Host "    $msg" -ForegroundColor Gray }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err2($msg) { Write-Host "    $msg" -ForegroundColor Red }

Write-Host "=================================================================" -ForegroundColor DarkCyan
Write-Host "  PCB DRC Intelligence -- native Windows startup (no Docker)" -ForegroundColor DarkCyan
Write-Host "=================================================================" -ForegroundColor DarkCyan

# ------------------------------------------------------------------
# 1. Locate a working Python 3.10+
# ------------------------------------------------------------------
Write-Step "Checking for Python 3.10+"

function Resolve-Python {
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3.13') },
        @{ Exe = 'py'; Args = @('-3.12') },
        @{ Exe = 'py'; Args = @('-3.11') },
        @{ Exe = 'py'; Args = @('-3.10') },
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() },
        @{ Exe = 'python3'; Args = @() }
    )
    foreach ($c in $candidates) {
        $found = Get-Command $c.Exe -ErrorAction SilentlyContinue
        if (-not $found) { continue }
        $verArgs = $c.Args + '--version'
        try {
            $verOut = & $c.Exe @verArgs 2>&1
        } catch { continue }
        if ($verOut -match 'Python (\d+)\.(\d+)') {
            $maj = [int]$Matches[1]; $min = [int]$Matches[2]
            if ($maj -gt 3 -or ($maj -eq 3 -and $min -ge 10)) {
                return $c
            }
        }
    }
    return $null
}

$py = Resolve-Python
if (-not $py) {
    Write-Err2 "Python 3.10 or newer was not found on PATH."
    Write-Err2 "Install it from https://www.python.org/downloads/ -- check the 'Add python.exe to PATH' box during setup -- then re-run start.bat."
    exit 1
}
$pyVerArgs = $py.Args + '--version'
$pyVersionString = (& $py.Exe @pyVerArgs 2>&1)
Write-Ok "Found $pyVersionString"

# ------------------------------------------------------------------
# 2. Locate Node.js / npm
# ------------------------------------------------------------------
Write-Step "Checking for Node.js"
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $nodeCmd -or -not $npmCmd) {
    Write-Err2 "Node.js (which includes npm) was not found on PATH."
    Write-Err2 "Install the LTS version from https://nodejs.org/, then re-run start.bat."
    exit 1
}
$nodeVersion = (& node --version)
Write-Ok "Found Node.js $nodeVersion"
if ($nodeVersion -match 'v(\d+)\.') {
    $nodeMajor = [int]$Matches[1]
    if ($nodeMajor -lt 20) {
        Write-Warn2 "Node.js 20+ is recommended for this project's frontend tooling (Vite 8). You have $nodeVersion -- if 'npm install' or the frontend fail below, upgrade Node.js and try again."
    }
}

# ------------------------------------------------------------------
# 3. Python virtual environment
# ------------------------------------------------------------------
Write-Step "Setting up Python virtual environment (.venv)"
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$venvPip = Join-Path $root '.venv\Scripts\pip.exe'

if (-not (Test-Path $venvPython)) {
    Write-Info2 "Creating .venv (this only happens once)..."
    $venvArgs = $py.Args + @('-m', 'venv', '.venv')
    & $py.Exe @venvArgs
    if (-not (Test-Path $venvPython)) {
        Write-Err2 "Failed to create the virtual environment. See the errors above."
        exit 1
    }
    Write-Ok "Virtual environment created."
} else {
    Write-Ok "Virtual environment already exists."
}

# ------------------------------------------------------------------
# 4. Backend dependencies (only reinstalled if pyproject.toml changed)
# ------------------------------------------------------------------
Write-Step "Installing backend dependencies (this can take a few minutes the first time)"
$depsMarker = Join-Path $root '.venv\.pcb_ai_deps.hash'
$currentHash = (Get-FileHash (Join-Path $root 'pyproject.toml') -Algorithm SHA256).Hash
$installNeeded = $true
if (Test-Path $depsMarker) {
    $previousHash = (Get-Content $depsMarker -Raw).Trim()
    if ($previousHash -eq $currentHash) { $installNeeded = $false }
}
if ($installNeeded) {
    & $venvPip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        Write-Err2 "pip install failed. See the errors above -- do you have an internet connection?"
        exit 1
    }
    Set-Content -Path $depsMarker -Value $currentHash -NoNewline
    Write-Ok "Backend dependencies installed."
} else {
    Write-Ok "Backend dependencies already up to date -- skipping."
}

# ------------------------------------------------------------------
# 5. .env file (first run: guide Gemini API key setup)
# ------------------------------------------------------------------
Write-Step "Checking configuration (.env)"
$envPath = Join-Path $root '.env'
$envExamplePath = Join-Path $root '.env.example'

if (-not (Test-Path $envPath)) {
    Copy-Item $envExamplePath $envPath
    (Get-Content $envPath) -replace '^CAF_MODEL_PROVIDER=vllm$', 'CAF_MODEL_PROVIDER=gemini' | Set-Content $envPath

    Write-Warn2 "No .env file found -- created one from .env.example, pre-set to use Gemini."
    Write-Host ""
    Write-Host "    A Notepad window will open. Find the line that starts with:" -ForegroundColor Yellow
    Write-Host "        GEMINI_API_KEY=" -ForegroundColor White
    Write-Host "    and paste your Gemini API key right after the '='. Get one at" -ForegroundColor Yellow
    Write-Host "        https://aistudio.google.com/apikey" -ForegroundColor White
    Write-Host "    Save the file (Ctrl+S), close Notepad, then come back here." -ForegroundColor Yellow
    Write-Host ""
    Start-Process notepad.exe $envPath
    Read-Host "    Press Enter here once you've saved your Gemini API key in Notepad"

    # Verify a key was actually entered; loop until it looks non-empty.
    $keyLine = Select-String -Path $envPath -Pattern '^GEMINI_API_KEY=(.+)$'
    while ((-not $keyLine) -or [string]::IsNullOrWhiteSpace($keyLine.Matches[0].Groups[1].Value)) {
        Write-Warn2 "GEMINI_API_KEY still looks empty in .env."
        $again = Read-Host "    Open Notepad again to add it? (Y/n)"
        if ($again -eq 'n' -or $again -eq 'N') { break }
        Start-Process notepad.exe $envPath
        Read-Host "    Press Enter here once you've saved your Gemini API key in Notepad"
        $keyLine = Select-String -Path $envPath -Pattern '^GEMINI_API_KEY=(.+)$'
    }
    Write-Ok ".env is ready."
} else {
    Write-Ok ".env already exists -- leaving it untouched."
}

# ------------------------------------------------------------------
# 6. Frontend dependencies (only reinstalled if package-lock.json changed)
# ------------------------------------------------------------------
Write-Step "Installing frontend dependencies (this can take a few minutes the first time)"
$frontendDir = Join-Path $root 'frontend'
$frontendMarker = Join-Path $frontendDir '.npm_install.hash'
$lockFile = Join-Path $frontendDir 'package-lock.json'
if (-not (Test-Path $lockFile)) { $lockFile = Join-Path $frontendDir 'package.json' }
$currentFrontendHash = (Get-FileHash $lockFile -Algorithm SHA256).Hash
$nodeModulesDir = Join-Path $frontendDir 'node_modules'

$frontendInstallNeeded = $true
if ((Test-Path $nodeModulesDir) -and (Test-Path $frontendMarker)) {
    $previousFrontendHash = (Get-Content $frontendMarker -Raw).Trim()
    if ($previousFrontendHash -eq $currentFrontendHash) { $frontendInstallNeeded = $false }
}

if ($frontendInstallNeeded) {
    Push-Location $frontendDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Err2 "npm install failed. See the errors above -- do you have an internet connection?"
            exit 1
        }
        Set-Content -Path $frontendMarker -Value $currentFrontendHash -NoNewline
        Write-Ok "Frontend dependencies installed."
    } finally {
        Pop-Location
    }
} else {
    Write-Ok "Frontend dependencies already up to date -- skipping."
}

# ------------------------------------------------------------------
# 7. Start backend + frontend (each in its own window; skip if already running)
# ------------------------------------------------------------------
function Test-HttpUp($url) {
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
        return ($resp.StatusCode -ge 200) -and ($resp.StatusCode -lt 500)
    } catch {
        return $false
    }
}

$logsDir = Join-Path $root 'results'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

Write-Step "Starting backend ($BackendUrl)"
if (Test-HttpUp "$BackendUrl/health") {
    Write-Ok "Backend is already running -- skipping."
} else {
    $backendLog = Join-Path $logsDir 'backend.log'
    $backendCmd = "`$Host.UI.RawUI.WindowTitle = 'PCB DRC Intelligence - Backend'; Set-Location '$root'; & '$venvPython' -m uvicorn pcb_ai.api.app:app --host 127.0.0.1 --port $BackendPort 2>&1 | Tee-Object -FilePath '$backendLog'"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd -WindowStyle Normal | Out-Null

    Write-Info2 "Waiting for the backend to come up..."
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Seconds 1
        if (Test-HttpUp "$BackendUrl/health") { $ready = $true; break }
    }
    if ($ready) {
        Write-Ok "Backend is up."
    } else {
        Write-Warn2 "Backend didn't respond within 40s. Check the 'PCB DRC Intelligence - Backend' window and $backendLog for errors."
    }
}

Write-Step "Starting frontend ($FrontendUrl)"
if (Test-HttpUp $FrontendUrl) {
    Write-Ok "Frontend is already running -- skipping."
} else {
    $frontendLog = Join-Path $logsDir 'frontend.log'
    $frontendCmd = "`$Host.UI.RawUI.WindowTitle = 'PCB DRC Intelligence - Frontend'; Set-Location '$frontendDir'; npm run dev 2>&1 | Tee-Object -FilePath '$frontendLog'"
    Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd -WindowStyle Normal | Out-Null

    Write-Info2 "Waiting for the frontend to come up..."
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-HttpUp $FrontendUrl) { $ready = $true; break }
    }
    if ($ready) {
        Write-Ok "Frontend is up."
    } else {
        Write-Warn2 "Frontend didn't respond within 30s. Check the 'PCB DRC Intelligence - Frontend' window and $frontendLog for errors."
    }
}

# ------------------------------------------------------------------
# 8. Open the app
# ------------------------------------------------------------------
Write-Step "Opening $FrontendUrl in your browser"
try {
    Start-Process $FrontendUrl
} catch {
    Write-Warn2 "Couldn't open a browser automatically -- open $FrontendUrl manually."
}

Write-Host ""
Write-Host "=================================================================" -ForegroundColor DarkCyan
Write-Host "  Ready!  Backend: $BackendUrl   Frontend: $FrontendUrl" -ForegroundColor Green
Write-Host "  Two separate windows are running the backend and frontend --" -ForegroundColor Gray
Write-Host "  leave them open while you use the app." -ForegroundColor Gray
Write-Host "  To stop everything, run stop.bat." -ForegroundColor Gray
Write-Host "=================================================================" -ForegroundColor DarkCyan
