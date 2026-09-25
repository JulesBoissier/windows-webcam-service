#Requires -RunAsAdministrator
# Stops the webcam service and removes it. Re-install with .\install_service.ps1

. "$PSScriptRoot\config.ps1"

if (!(Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)) {
    Write-Output "Service '$ServiceName' is not installed."
    exit 0
}

Write-Output "Stopping service '$ServiceName'..."
Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue

Write-Output "Removing service '$ServiceName'..."
if (Test-Path $NssmPath) {
    & $NssmPath remove $ServiceName confirm
} else {
    sc.exe delete $ServiceName
}

Write-Output "Webcam service stopped and removed."
