#Requires -RunAsAdministrator
# Stops the webcam server and removes its scheduled task. Re-install with .\install_service.ps1
# Usage: .\stop_service.ps1 [-Port 8001]

param(
    [int]$Port = 0  # 0 means use $DefaultPort from config.ps1
)

. "$PSScriptRoot\config.ps1"
if ($Port -eq 0) { $Port = $DefaultPort }

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Output "Stopping scheduled task '$TaskName'..."
    Stop-ScheduledTask -TaskName $TaskName
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Scheduled task removed."
} else {
    Write-Output "Scheduled task '$TaskName' is not installed."
}

Remove-LegacyService
Stop-PortListeners $Port

Write-Output "Webcam server stopped."
