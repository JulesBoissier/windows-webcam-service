#Requires -RunAsAdministrator
# Restarts the webcam service, e.g. after pulling code changes.
# Re-run .\install_service.ps1 instead if requirements.txt or the port changed.

. "$PSScriptRoot\config.ps1"

if (!(Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    Write-Error "Service '$ServiceName' is not installed. Run .\install_service.ps1 first."
    exit 1
}

Write-Output "Restarting '$ServiceName'..."
Restart-Service -Name $ServiceName -Force
Get-Service -Name $ServiceName
