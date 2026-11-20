"""``/snapshot``: one fresh frame per request, from the background frame grabber.

These tests run the app with its lifespan (``with TestClient(...)``), which starts the
grabber thread, against ``LiveCapture``, a fake camera that produces numbered frames and
records when each one was read.
"""

import threading
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main


class LiveCapture:
    """Fake camera: frame k is solid grey level 10 + k, read every ``interval`` seconds."""

    def __init__(self, interval=0.01, working=True):
        self.interval = interval
        self.working = working
        self.read_times = []
        self._lock = threading.Lock()

    def isOpened(self):
        return True

    def read(self):
        time.sleep(self.interval)
        if not self.working:
            return False, None
        with self._lock:
            k = len(self.read_times)
            self.read_times.append(time.monotonic())
        return True, np.full((60, 80, 3), 10 + k, dtype=np.uint8)

    def release(self):
        pass

    def set(self, prop, value):
        return True

    def get(self, prop):
        return 0


def frame_number(jpeg: bytes) -> int:
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    return int(round(float(image.mean()))) - 10


@pytest.fixture
def live(monkeypatch):
    camera = LiveCapture()
    monkeypatch.setattr(main, "cap", camera)
    with TestClient(main.app) as client:
        time.sleep(0.1)  # let a few frames go by, as on a running service
        yield client, camera


def test_snapshot_returns_a_frame_captured_after_the_request(live):
    """The frame ``/snapshot`` returns was read from the camera after the request arrived.

    Why: the orchestrator captures a calibration frame when the user presses ENTER on a
    dot. With the old ``/video_feed``, the first frame of a new stream could come from
    OpenCV's buffer, captured before the user looked at the dot, which mislabels
    calibration data. ``/snapshot`` waits for the next frame instead.
    """
    client, camera = live

    requested = time.monotonic()
    r = client.get("/snapshot")

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    k = frame_number(r.content)
    assert camera.read_times[k] > requested
    assert int(r.headers["x-frame-delay-ms"]) >= 0


def test_consecutive_snapshots_are_different_frames(live):
    """Two snapshots in a row return two different, increasingly recent frames.

    Why: each tick and each calibration dot must get its own image, never a cached one.
    """
    client, _ = live

    first = frame_number(client.get("/snapshot").content)
    second = frame_number(client.get("/snapshot").content)

    assert second > first


def test_snapshot_without_camera_is_service_unavailable(monkeypatch):
    """When the camera can't be read, ``/snapshot`` answers 503 after a short wait.

    Why: an unplugged camera, or one held by another app, must surface quickly and
    clearly. The orchestrator records a gap and tries again next tick rather than
    hanging.
    """
    monkeypatch.setattr(main, "cap", LiveCapture(working=False))
    monkeypatch.setattr(main, "FRAME_TIMEOUT_S", 0.3)
    monkeypatch.setattr(main, "RETRY_DELAY_S", 0.05)

    with TestClient(main.app) as client:
        started = time.monotonic()
        r = client.get("/snapshot")

    assert r.status_code == 503
    assert time.monotonic() - started < 2
