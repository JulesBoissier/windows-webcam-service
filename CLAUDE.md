# windows-webcam-service

Tiny FastAPI app that exposes the Windows host's default webcam (`cv2.VideoCapture(0)`) as an MJPEG stream. Part of the attention-tracking system — see `../CLAUDE.md` for how it fits with the other repos. Its only consumer is `activity-orchestration-client/src/backend/clients/windows_webcam_client.py`.

## Layout

Everything is in `main.py`; `install_service.ps1` installs it as a Windows service. No pre-commit yet.

## Routes

- `GET /` — info blob (`version`/`uptime` are empty placeholders).
- `GET /health` — `{"status": "ok"}`; used by the orchestrator's health check.
- `GET /video_feed` — `multipart/x-mixed-replace; boundary=frame` stream of JPEG frames, generated forever until the camera read fails or the client disconnects.

## Tests

```bash
pip install -r requirements-dev.txt   # plus requirements.txt on Windows
pytest
```

`tests/test_api.py::FakeCapture` replaces `main.cap`, so no camera is needed and the suite runs on Linux too. CI (`.github/workflows/python-ci.yml`) runs on `windows-latest`. Docstrings explain what each test covers and why the behaviour is designed that way. `xfail(strict=True)` marks bugs fixed on `fix/install-scripts`; remove each marker when merging that fix.

## Running

Windows only (DirectShow camera access, NSSM). It can't run from WSL/Linux, but its tests can (see above).

```powershell
# dev
py main.py --port 8001
# install as Windows service (admin PowerShell). Pass the port explicitly — see gotchas.
.\install_service.ps1 -Port 8001
```

The install script downloads NSSM into the repo folder, creates `venv\`, installs requirements, (re)registers the `WindowsWebcamService` NSSM service and starts it.

## Design notes

- **Runs as a real Windows service (NSSM)** — unlike the watchdog, camera access works from Session 0, so it can start at boot with no user logged in.
- **Pull model, single global `VideoCapture`.** The camera is opened once at import time and shared by all requests. The orchestrator opens a stream, reads one frame and disconnects every cycle, so the stream is effectively used as "get latest frame".
- Binds `0.0.0.0` so the orchestrator can reach it from WSL/Docker.

## Gotchas

- **Default port mismatch on `main`:** `main.py` defaults to 8001 (what the client expects) but `install_service.ps1` defaults to **8002**, colliding with the watchdog. Fixed on `fix/install-scripts` (adds `config.ps1` with `$DefaultPort = 8001`).
- **`requirements.txt` is UTF-16 LE with BOM** on `main`. Preserve or deliberately convert the encoding when editing.
- `cv2.VideoCapture` is not thread-safe; concurrent `/video_feed` requests share it unguarded, and nothing reopens the camera if it's unplugged or grabbed by another app. Both fixed on `fix/install-scripts` (`cap_lock` + `read_frame()` reopen) — merge that rather than re-implementing.
- If the camera read fails the generator just ends, so the client sees an empty stream and `get_camera_input()` returns `None`.
