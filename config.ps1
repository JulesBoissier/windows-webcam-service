# Shared settings, dot-sourced by the *_service.ps1 scripts.

$DefaultPort      = 8001
$TaskName         = "WindowsWebcamService"
$ProjectDir       = $PSScriptRoot
$MainScript       = "$ProjectDir\main.py"
$RequirementsFile = "$ProjectDir\requirements.txt"
$VenvPath         = "$ProjectDir\venv"
$PythonExe        = "$VenvPath\Scripts\python.exe"
$PythonwExe       = "$VenvPath\Scripts\pythonw.exe"  # No console window
$LogFile          = "$ProjectDir\webcam.log"

# Earlier versions ran as an NSSM Windows service under this name. The install and
# stop scripts remove it if it's still there.
$LegacyServiceName = "WindowsWebcamService"
$NssmPath          = "$ProjectDir\nssm.exe"

# Checked with sc.exe rather than Get-Service: a ServiceController object keeps a handle
# open, and an open handle is what leaves a deleted service stuck "marked for deletion".
function Test-LegacyService {
    sc.exe query $LegacyServiceName | Out-Null
    return $LASTEXITCODE -ne 1060  # 1060: service does not exist
}

function Remove-LegacyService {
    if (!(Test-LegacyService)) { return }
    Write-Output "Removing the old '$LegacyServiceName' Windows service..."
    sc.exe stop $LegacyServiceName | Out-Null
    if (Test-Path $NssmPath) {
        & $NssmPath remove $LegacyServiceName confirm | Out-Null
    } else {
        sc.exe delete $LegacyServiceName | Out-Null
    }
    if (Test-LegacyService) {
        Write-Warning ("Windows has marked '$LegacyServiceName' for deletion but something still " +
            "holds it open (services.msc, Task Manager, or another PowerShell window). It is " +
            "harmless while stopped and disappears once those are closed, or after a reboot.")
    }
}

function Stop-PortListeners([int]$Port) {
    # Catches copies started outside the task: by hand, or by an older install.
    $Listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($Conn in $Listeners) {
        $Proc = Get-Process -Id $Conn.OwningProcess -ErrorAction SilentlyContinue
        if ($Proc -and $Proc.ProcessName -like "python*") {
            Write-Output "Stopping $($Proc.ProcessName) (PID $($Proc.Id)) on port $Port..."
            Stop-Process -Id $Proc.Id -Force
        }
    }
}
