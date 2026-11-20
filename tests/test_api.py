"""The webcam service's HTTP contract with the orchestrator.

``activity-orchestration-client/src/backend/clients/windows_webcam_client.py`` reads
``/video_feed``. These tests replace the camera with ``FakeCapture`` so they run without a
webcam, on any OS.
"""

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

import main


class FakeCapture:
    """Stands in for ``cv2.VideoCapture``: yields the given frames, then reports read failure."""

    def __init__(self, frames, opened=True):
        self.frames = list(frames)
        self.opened = opened

    def isOpened(self):
        return self.opened

    def read(self):
        if not self.opened or not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self):
        self.opened = False

    def set(self, prop, value):  # the service configures every camera it opens
        return True

    def get(self, prop):
        return 0


def frames(n):
    yy, xx = np.mgrid[0:120, 0:160]
    return [np.dstack([xx + 40 * i, yy, xx + yy]).astype(np.uint8) for i in range(n)]


def jpeg_parts(body: bytes):
    """Split a multipart body into decoded JPEG images."""
    parts = []
    for chunk in body.split(b"--frame\r\n")[1:]:
        header, _, payload = chunk.partition(b"\r\n\r\n")
        assert b"Content-Type: image/jpeg" in header
        image = cv2.imdecode(np.frombuffer(payload.rstrip(b"\r\n"), np.uint8), cv2.IMREAD_COLOR)
        parts.append(image)
    return parts


@pytest.fixture
def api():
    return TestClient(main.app)


def test_health(api):
    """``GET /health`` answers 200 with ``{"status": "ok"}``.

    Why: the orchestrator checks this before every tick and refuses to track without it.
    """
    r = api.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_video_feed_streams_camera_frames_as_mjpeg(api, monkeypatch):
    """``/video_feed`` streams each camera frame, in order, as a JPEG part of an MJPEG stream.

    Why: MJPEG (``multipart/x-mixed-replace; boundary=frame``) can be opened directly in a
    browser for debugging, and the orchestrator takes the first frame of it each tick.
    """
    source = frames(3)
    monkeypatch.setattr(main, "cap", FakeCapture(source))

    r = api.get("/video_feed")

    assert r.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
    images = jpeg_parts(r.content)
    assert len(images) == 3
    for got, sent in zip(images, source):
        assert got.shape == sent.shape
        assert np.abs(got.astype(int) - sent.astype(int)).mean() < 10  # JPEG-lossy


def test_stream_ends_when_camera_fails(api, monkeypatch):
    """When the camera can't be read the stream ends instead of hanging.

    Why: an unplugged camera (or one taken by another app) must surface to the client as
    "no frame" quickly. The orchestrator then records a gap and tries again next tick.
    """
    monkeypatch.setattr(main, "cap", FakeCapture([], opened=True))

    r = api.get("/video_feed")

    assert r.status_code == 200
    assert jpeg_parts(r.content) == []


def test_reopens_camera_that_was_closed(api, monkeypatch):
    """If the capture device was closed (unplugged, grabbed by another app), it's reopened.

    Why: the service runs unattended for days. Without reopening, one disconnect breaks
    tracking until someone restarts the Windows service.
    """
    monkeypatch.setattr(main, "cap", FakeCapture([], opened=False))
    monkeypatch.setattr(main.cv2, "VideoCapture", lambda index: FakeCapture(frames(1)))

    r = api.get("/video_feed")

    assert len(jpeg_parts(r.content)) == 1
