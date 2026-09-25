# windows-webcam-server
A Windows Service that streams webcam captures

Runs as a Windows service via [NSSM](https://nssm.cc) and serves on port **8001** by default.

## Scripts

Run from an **administrator** PowerShell in this folder (`status_service.ps1` doesn't need admin):

| Script | What it does |
| --- | --- |
| `.\install_service.ps1 [-Port 8001]` | Downloads NSSM, creates the venv, installs dependencies, installs and starts the service |
| `.\status_service.ps1` | Shows service state, `/health` result and the last lines of `webcam.log` |
| `.\restart_service.ps1` | Restarts the service, e.g. after pulling code changes |
| `.\stop_service.ps1` | Stops the service and removes it |

Requires Python 3 on PATH (`py` or `python`). Re-run `install_service.ps1` after changing `requirements.txt` or the port. Shared names and paths live in `config.ps1`.
