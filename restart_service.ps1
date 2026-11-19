#Requires -RunAsAdministrator
# Restarts the webcam server, e.g. after pulling code changes.
# Re-run .\install_service.ps1 instead if requirements.txt or the port changed.

. "$PSScriptRoot\config.ps1"

if (!(Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    Write-Error "Scheduled task '$TaskName' is not installed. Run .\install_service.ps1 first."
    exit 1
}

Write-Output "Restarting '$TaskName'..."
Stop-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 1
Start-ScheduledTask -TaskName $TaskName
Write-Output "Restarted. Run .\status_service.ps1 to check it came up."
