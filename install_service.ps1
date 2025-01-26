# PowerShell script to set up a Windows service for a Python project using NSSM

# Step 1: Set variables
$ProjectDir = $PSScriptRoot  # The directory where this script is located
$PythonExe = "$ProjectDir\venv\Scripts\python.exe"
$MainScript = "$ProjectDir\main.py"
$RequirementsFile = "$ProjectDir\requirements.txt"
$ServiceName = "WebcamService"
$NssmPath = "$ProjectDir\nssm.exe"

# Step 2: Check if NSSM is present, if not, download it
if (!(Test-Path $NssmPath)) {
    Write-Output "NSSM not found, downloading..."
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile "$ProjectDir\nssm.zip"
    
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
if (!(Test-Path "$ProjectDir\venv")) {
    Write-Output "Creating virtual environment..."
    python -m venv "$ProjectDir\venv"
}

# Step 4: Install required dependencies
Write-Output "Installing dependencies..."
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r $RequirementsFile

# Step 5: Remove existing service (if any)
Write-Output "Removing existing service (if exists)..."
& $NssmPath remove $ServiceName confirm

# Step 6: Install the service with NSSM
Write-Output "Installing the Windows service..."
& $NssmPath install $ServiceName $PythonExe $MainScript

# Step 7: Start the service
Write-Output "Starting the service..."
& $NssmPath start $ServiceName

# Step 8: Check if the service is running
Write-Output "Checking service status..."
Get-Service -Name $ServiceName

Write-Output "Setup completed! FastAPI should be running at http://127.0.0.1:8000"
