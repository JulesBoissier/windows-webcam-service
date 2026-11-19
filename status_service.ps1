# Shows whether the webcam service is installed, running and healthy, plus recent log lines.
# Usage: .\status_service.ps1 [-Port 8001] [-Lines 20]

param(
    [int]$Port = 0,  # 0 means use $DefaultPort from config.ps1
    [int]$Lines = 20
)

. "$PSScriptRoot\config.ps1"
if ($Port -eq 0) { $Port = $DefaultPort }

$Service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($Service) {
    Write-Output "Service:  $($Service.Status) (startup $($Service.StartType))"
} else {
    Write-Output "Service:  not installed"
}

try {
    $Health = Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 3
    Write-Output "Health:   $($Health.status) at http://127.0.0.1:$Port"
} catch {
    Write-Output "Health:   not responding on port $Port"
}

if (Test-Path $LogFile) {
    Write-Output "`nLast $Lines lines of ${LogFile}:"
    Get-Content $LogFile -Tail $Lines
} else {
    Write-Output "Log:      no log file yet at $LogFile"
}
