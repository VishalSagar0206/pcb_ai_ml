<#
.SYNOPSIS
  Stops the PCB DRC Intelligence backend and frontend dev servers started
  by start.ps1.

.DESCRIPTION
  Finds whatever process is actually listening on the backend (8931) and
  frontend (5173) ports and stops it -- rather than relying on remembered
  process IDs, so this works even if a console window was closed abruptly
  or the machine was restarted without a clean shutdown.

  Normally launched via ..\..\stop.bat (double-click), not run directly.
#>

$ErrorActionPreference = 'SilentlyContinue'

$BackendPort = 8931
$FrontendPort = 5173

function Write-Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Write-Info2($msg) { Write-Host "    $msg" -ForegroundColor Gray }

function Stop-Port {
    param([int]$Port, [string]$Label)

    Write-Step "Stopping $Label (port $Port)"
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
        Write-Info2 "Nothing is listening on port $Port -- nothing to stop."
        return
    }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Info2 "Stopping $($proc.ProcessName) (PID $procId)..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Ok "$Label stopped."
}

Write-Host "=================================================================" -ForegroundColor DarkCyan
Write-Host "  PCB DRC Intelligence -- stopping backend and frontend" -ForegroundColor DarkCyan
Write-Host "=================================================================" -ForegroundColor DarkCyan

Stop-Port -Port $BackendPort -Label "backend"
Stop-Port -Port $FrontendPort -Label "frontend"

Write-Host ""
Write-Host "Done. Any leftover backend/frontend console windows can now be closed." -ForegroundColor Green
