# windows-webcam-service

Tiny FastAPI app that exposes the Windows host's default webcam (`cv2.VideoCapture(0)`) as an MJPEG stream. Part of the attention-tracking system — see `../CLAUDE.md` for how it fits with the other repos. Its only consumer is `activity-orchestration-client/src/backend/clients/windows_webcam_client.py`.

## Layout

- `main.py` — the whole app: FastAPI routes, a shared `VideoCapture` guarded by `cap_lock`, `read_frame()` that reopens a closed camera, `FrameGrabber` (background thread started by the app's lifespan), argparse (`--port`, `--log-file`).
- `config.ps1` — shared names and paths, dot-sourced by the scripts below; also holds the legacy-service cleanup helpers.
- `install_service.ps1` / `stop_service.ps1` / `restart_service.ps1` / `status_service.ps1` — manage the `WindowsWebcamService` **scheduled task**. Despite the file names, there is no Windows service any more; the names are kept so the commands match the watchdog's.

No pre-commit yet.

## Routes

- `GET /` — info blob, including `resolution: {requested, actual}` (`version`/`uptime` are empty placeholders).
- `GET /health` — `{"status": "ok"}`; used by the orchestrator's health check.
- `GET /snapshot` — **one JPEG frame captured after the request arrived** (`image/jpeg`, header `X-Frame-Delay-Ms`); 503 if no frame within `FRAME_TIMEOUT_S`. This is what the orchestrator uses.
- `GET /frame_at?t=<unix time>` — the recorded JPEG closest to `t` (header `X-Frame-Time`), for implicit calibration from clicks (`t` comes from the watchdog's `/clicks`, same Windows clock). The first request turns on `FrameHistory` (~10 fps, last 5 s, ~5 MB at 720p); 404 if no frame within 0.25 s.
- `GET /video_feed` — `multipart/x-mixed-replace; boundary=frame` stream of JPEG frames until the camera fails or the client disconnects. Kept for browser debugging and older clients.

## Tests

```bash
pip install -r requirements-dev.txt   # plus requirements.txt on Windows
pytest
```

`tests/test_api.py::FakeCapture` replaces `main.cap`, so no camera is needed and the suite runs on Linux too. CI (`.github/workflows/python-ci.yml`) runs on `windows-latest`. Docstrings explain what each test covers and why the behaviour is designed that way.

## Running

Windows only (DirectShow camera access). It can't run from WSL/Linux, but its tests can (see above).

```powershell
venv\Scripts\python main.py --port 8001     # foreground, for debugging
.\install_service.ps1                        # admin PowerShell: logon task on port 8001
.\status_service.ps1                         # task state, /health, tail of webcam.log
```

`install_service.ps1` creates `venv\`, installs requirements, removes the old NSSM service and any process already on the port, registers a logon task running `venv\Scripts\pythonw.exe main.py --log-file webcam.log` as the current user, and starts it.

## Design notes

- **Runs as a scheduled task at logon, not a Windows service.** It used to be an NSSM service running as LocalSystem in session 0. That broke in two ways: LocalSystem can't start a Microsoft Store or per-user Python (the venv launcher fails with "The file cannot be accessed by the system", error 1920, and NSSM shows the service as *Paused*), and camera privacy settings are per user. A logon task runs as the user, in their session, the same way the watchdog does. The cost is that it only runs while the user is logged in, which is the only time the tracker is useful anyway.
- **`--log-file`** exists because the task runs `pythonw.exe` (no console window), where `sys.stdout`/`sys.stderr` are `None` and uvicorn's logging would crash. A task action isn't a shell, so output can't be redirected with `>`.
- **Background grabber, fresh snapshots.** OpenCV buffers a few frames, so the first frame of a newly opened stream can predate the request (e.g. come from before the user looked at a calibration dot). `FrameGrabber` reads the camera continuously, keeping that buffer empty, and `/snapshot` waits for the first frame read *after* the request. Cost: the camera is read at full frame rate all the time (it was already held open). Without the lifespan (e.g. `TestClient(app)` outside a `with`), the grabber isn't running and `/video_feed` reads the camera directly; the older tests rely on that.
- **1280×720 MJPG by default** (`open_camera()`, `REQUESTED_SIZE`, `--width/--height`). At OpenCV's default 640×480 the face is ~120 px wide. Cameras may deliver another size; `GET /` shows the actual one. Costs ~50% more gaze-model time per frame in the vision service (181 → 272 ms measured). Calibration profiles stay valid across resolutions (the vision service measures face width relative to image width).
- Binds `0.0.0.0` so the orchestrator can reach it from WSL/Docker.

## Gotchas

- **Only one process can hold the camera.** A copy left running in a terminal, or the old NSSM service, makes the task's stream come back empty. `install_service.ps1` and `stop_service.ps1` clean up both; `status_service.ps1` warns if the old service still exists.
- **"Marked for deletion":** Windows only finishes deleting a service once nothing holds a handle to it (services.msc, Task Manager, a PowerShell window that ran `Get-Service`). The scripts check the old service with `sc.exe` for this reason. A stuck one is harmless while stopped and goes away after a reboot.
- **`requirements.txt` is UTF-16 LE with BOM** on `main`; this branch's copy is UTF-8. Preserve or deliberately convert the encoding when editing.
- If the camera read fails the generator just ends, so the client sees an empty stream and `get_camera_input()` returns `None`.
