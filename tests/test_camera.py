"""How the service opens the camera."""

import cv2
from fastapi.testclient import TestClient

import main


class RecordingCapture:
    """Fake ``cv2.VideoCapture`` that records requested properties and reports what it 'delivers'."""

    def __init__(self, index, delivers=(1280, 720)):
        self.requested = {}
        self.delivers = delivers

    def set(self, prop, value):
        self.requested[prop] = value
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FRAME_WIDTH: self.delivers[0], cv2.CAP_PROP_FRAME_HEIGHT: self.delivers[1]}.get(prop, 0)

    def isOpened(self):
        return True

    def release(self):
        pass


def test_camera_is_opened_at_720p_with_mjpg(monkeypatch):
    """The camera is asked for 1280x720 in MJPG.

    Why: at OpenCV's default 640x480 the face is ~120 px wide and the eyes a few pixels,
    which limits the gaze model. MJPG is what most webcams need to deliver 720p at full
    frame rate.
    """
    monkeypatch.setattr(main.cv2, "VideoCapture", RecordingCapture)

    camera = main.open_camera()

    assert camera.requested[cv2.CAP_PROP_FRAME_WIDTH] == 1280
    assert camera.requested[cv2.CAP_PROP_FRAME_HEIGHT] == 720
    assert camera.requested[cv2.CAP_PROP_FOURCC] == cv2.VideoWriter_fourcc(*"MJPG")


def test_root_reports_the_resolution_actually_delivered(monkeypatch):
    """``GET /`` shows the requested and the actual frame size.

    Why: cameras silently fall back to sizes they support. Knowing what is really
    delivered matters, because calibration profiles should be recorded at the size used
    for tracking.
    """
    monkeypatch.setattr(main, "cap", RecordingCapture(0, delivers=(640, 480)))

    body = TestClient(main.app).get("/").json()

    assert body["resolution"] == {"requested": [1280, 720], "actual": [640, 480]}
