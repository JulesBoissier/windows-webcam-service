# Shared settings, dot-sourced by the *_service.ps1 scripts.

$DefaultPort      = 8001
$ServiceName      = "WindowsWebcamService"
$ProjectDir       = $PSScriptRoot
$MainScript       = "$ProjectDir\main.py"
$RequirementsFile = "$ProjectDir\requirements.txt"
$NssmPath         = "$ProjectDir\nssm.exe"
$VenvPath         = "$ProjectDir\venv"
$PythonExe        = "$VenvPath\Scripts\python.exe"
$LogFile          = "$ProjectDir\webcam.log"
