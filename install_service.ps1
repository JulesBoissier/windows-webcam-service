#Requires -RunAsAdministrator
# PowerShell script to set up a Windows service for a Python project using NSSM
# Usage: .\install_service.ps1 [-Port 8001]

param(
    [int]$Port = 0  # 0 means use $DefaultPort from config.ps1
)

# Step 1: Load shared settings
. "$PSScriptRoot\config.ps1"
if ($Port -eq 0) { $Port = $DefaultPort }

# Step 2: Check if NSSM is present, if not, download it
if (!(Test-Path $NssmPath)) {
    Write-Output "NSSM not found, downloading..."
    try {
        Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$ProjectDir\nssm.zip" -UseBasicParsing
    } catch {
        Write-Error "Could not download NSSM ($_). Download nssm-2.24.zip manually and put win64\nssm.exe in $ProjectDir"
        exit 1
    }

    # Extract NSSM
    Expand-Archive -Path "$ProjectDir\nssm.zip" -DestinationPath "$ProjectDir\nssm_temp" -Force
    Move-Item -Path "$ProjectDir\nssm_temp\nssm-2.24\win64\nssm.exe" -Destination $NssmPath -Force

    # Cleanup
    Remove-Item -Path "$ProjectDir\nssm.zip" -Force
    Remove-Item -Path "$ProjectDir\nssm_temp" -Recurse -Force

    Write-Output "NSSM installed at: $NssmPath"
} else {
    Write-Output "NSSM is already present."
}

# Step 3: Create Virtual Environment if not exists
if (!(Test-Path $PythonExe)) {
    # Use the py launcher if installed, otherwise fall back to python on PATH
    $PythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
    Write-Output "Creating virtual environment with '$PythonCmd'..."
    & $PythonCmd -m venv $VenvPath
}

if (!(Test-Path $PythonExe)) {
    Write-Error "Virtual environment creation failed: $PythonExe not found. Is Python installed?"
    exit 1
}

# Step 4: Install required dependencies
Write-Output "Installing dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r $RequirementsFile
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dependency installation failed. Fix the pip error above and re-run."
    exit 1
}

# Step 5: Stop and remove existing service (if any)
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Output "Removing existing service..."
    & $NssmPath stop $ServiceName | Out-Null
    & $NssmPath remove $ServiceName confirm
}

# Step 6: Install the service with NSSM, logging to a rotating file
Write-Output "Installing the Windows service..."
& $NssmPath install $ServiceName $PythonExe $MainScript "--port" "$Port"
& $NssmPath set $ServiceName AppDirectory $ProjectDir | Out-Null
& $NssmPath set $ServiceName AppStdout $LogFile | Out-Null
& $NssmPath set $ServiceName AppStderr $LogFile | Out-Null
& $NssmPath set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmPath set $ServiceName AppRotateBytes 1048576 | Out-Null

# Step 7: Start the service
Write-Output "Starting the service..."
& $NssmPath start $ServiceName
Start-Sleep -Seconds 3

# Step 8: Check the service is running and healthy
Get-Service -Name $ServiceName
try {
    Invoke-RestMethod "http://127.0.0.1:$Port/health" -TimeoutSec 5 | Out-Null
    Write-Output "Setup completed! Webcam service is running at http://127.0.0.1:$Port"
} catch {
    Write-Warning "Service started but http://127.0.0.1:$Port/health is not responding yet. Check $LogFile or run .\status_service.ps1"
}
