"""How the server behaves when started the way the logon task starts it."""

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_log_file_captures_server_output_without_a_console(tmp_path):
    """With ``--log-file`` and no console streams, the server starts and logs to the file.

    Why: the logon task runs ``pythonw.exe``, which has no console, so ``sys.stdout`` and
    ``sys.stderr`` are ``None``. Uvicorn crashes writing its startup log to them unless
    output goes to a file, and a task action can't redirect output itself. This runs
    ``main.py`` with both streams set to ``None``, exactly as under ``pythonw.exe``, and
    checks it gets as far as serving.
    """
    log = tmp_path / "webcam.log"
    pythonw = (
        "import runpy, sys; sys.stdout = sys.stderr = None; "
        f"sys.argv = ['main.py', '--port', '0', '--log-file', {str(log)!r}]; "
        "runpy.run_path('main.py', run_name='__main__')"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", pythonw],
        cwd=REPO,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline and proc.poll() is None:
            if log.exists() and "Uvicorn running" in log.read_text(errors="replace"):
                break
            time.sleep(0.2)
        assert proc.poll() is None, f"server exited early:\n{log.read_text() if log.exists() else ''}"
        assert "Uvicorn running" in log.read_text(errors="replace")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
