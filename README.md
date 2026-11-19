# windows-webcam-server
Streams webcam captures over HTTP (MJPEG) for the attention tracker.

Runs as a scheduled task in your desktop session at logon and serves on port **8001** by default.

It used to be an NSSM Windows service. Services run as LocalSystem in session 0, an account that can't start a per-user or Microsoft Store Python and isn't covered by your camera privacy settings. A logon task runs as you, in your session, like the system watchdog.

## Scripts

Run from an **administrator** PowerShell in this folder (`status_service.ps1` doesn't need admin):

| Script | What it does |
| --- | --- |
| `.\install_service.ps1 [-Port 8001]` | Creates the venv, installs dependencies, removes the old NSSM service if present, registers the logon task and starts it |
| `.\status_service.ps1` | Shows task state, `/health` result and the last lines of `webcam.log` |
| `.\restart_service.ps1` | Restarts the task, e.g. after pulling code changes |
| `.\stop_service.ps1` | Stops the server and removes the scheduled task (and the old service, if present) |

Requires Python 3 on PATH (`py` or `python`). Re-run `install_service.ps1` after changing `requirements.txt` or the port. Shared names and paths live in `config.ps1`.

To check the camera, open http://127.0.0.1:8001/video_feed in a browser.

To run it in the foreground instead (stop the task first): `venv\Scripts\python main.py --port 8001`.
