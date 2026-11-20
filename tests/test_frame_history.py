"""``/frame_at``: frames from a given moment, for implicit calibration from clicks."""

import time

import pytest
from fastapi.testclient import TestClient

import main
from main import FrameHistory
from tests.test_snapshot import LiveCapture


def test_history_keeps_recent_frames_and_finds_the_closest():
    """The history keeps about one frame per interval for a few seconds and returns the frame nearest a time.

    Why: a click is reported after it happens; the frame the user saw while clicking has
    to be looked up afterwards. Keeping only ~10 fps for 5 s bounds memory (~5 MB at 720p).
    """
    history = FrameHistory(seconds=1.0, interval=0.1)
    for i in range(30):  # 30 fps for 1 s
        t = 1000.0 + i / 30
        if history.due(t):
            history.add(t, f"f{i}".encode())

    assert 9 <= len(history._frames) <= 11
    t, jpeg = history.closest(1000.5)
    assert abs(t - 1000.5) <= 0.06
    assert history.closest(1003.0) is None  # nowhere near any stored frame


def test_history_forgets_old_frames():
    """Frames older than the history window are dropped.

    Why: memory stays bounded however long the service runs.
    """
    history = FrameHistory(seconds=1.0, interval=0.1)
    for i in range(50):
        history.add(1000.0 + i * 0.1, b"x")

    assert history.closest(1000.0) is None
    assert history.closest(1004.9) is not None


@pytest.fixture
def live(monkeypatch):
    camera = LiveCapture(interval=0.01)
    monkeypatch.setattr(main, "cap", camera)
    monkeypatch.setattr(main.grabber, "history", None)
    with TestClient(main.app) as client:
        yield client


def test_frame_at_returns_the_frame_from_that_moment(live):
    """``/frame_at?t=`` returns the recorded JPEG closest to ``t``, with its time in ``X-Frame-Time``.

    Why: the orchestrator pairs each click (time from the watchdog, same Windows clock)
    with what the camera saw at that moment, which is when the user was looking at the
    click target.
    """
    live.get("/frame_at", params={"t": time.time()})  # turns history on
    time.sleep(0.6)
    t = time.time() - 0.3

    r = live.get("/frame_at", params={"t": t})

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert abs(float(r.headers["x-frame-time"]) - t) <= 0.1


def test_frame_at_before_history_is_not_found(live):
    """A time from before history started (or long ago) answers 404.

    Why: history is only recorded once implicit calibration asks for it; older clicks have
    no frame and must be skipped, not paired with the wrong image.
    """
    live.get("/frame_at", params={"t": time.time()})

    assert live.get("/frame_at", params={"t": time.time() - 60}).status_code == 404
