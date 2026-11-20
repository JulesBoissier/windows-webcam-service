import argparse
import sys
import threading
import time
from contextlib import asynccontextmanager

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse

# Requested capture size. OpenCV's default is usually 640x480, where the face is only
# ~120 px wide and the eyes a few pixels; a larger face crop gives the gaze model more to
# work with. The camera may deliver a different size: see camera_info().
REQUESTED_SIZE = (1280, 720)


def open_camera():
    """Open the default camera, asking for MJPG at REQUESTED_SIZE.

    Many USB webcams only reach 720p at full frame rate with MJPG; uncompressed (YUY2)
    720p is often limited to ~10 fps.
    """
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, REQUESTED_SIZE[0])
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, REQUESTED_SIZE[1])
    return camera


def camera_info() -> dict:
    """What the camera actually delivers (it may not honour the requested size)."""
    with cap_lock:
        return {
            "requested": list(REQUESTED_SIZE),
            "actual": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))],
        }


cap = open_camera()
cap_lock = threading.Lock()  # VideoCapture is not thread-safe across requests

# How long /snapshot and /video_feed wait for a new frame before giving up.
FRAME_TIMEOUT_S = 2.0
# Pause between attempts while the camera can't be read (unplugged, in use elsewhere).
RETRY_DELAY_S = 0.5


def read_frame():
    global cap
    with cap_lock:
        if not cap.isOpened():
            # Camera was unplugged or grabbed by another app; try to reopen it
            cap.release()
            cap = open_camera()
        return cap.read()


class FrameGrabber:
    """Reads the camera continuously on a background thread and keeps the latest frame.

    OpenCV buffers a few frames inside the capture device. A client that opens a stream
    and takes the first frame can get one captured before it asked, e.g. before the user
    looked at a calibration dot. Reading continuously keeps that buffer empty, so
    "the next frame" is always a fresh one.
    """

    def __init__(self):
        self._frame = None
        self._time = 0.0  # time.monotonic() when the latest frame was read
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="frame-grabber", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def _run(self):
        while not self._stop.is_set():
            ok, frame = read_frame()
            if not ok:
                self._stop.wait(RETRY_DELAY_S)
                continue
            with self._cond:
                self._frame = frame
                self._time = time.monotonic()
                self._cond.notify_all()

    def next_frame(self, after: float, timeout: float = None):
        """Return ``(frame, read_time)`` for the first frame read after ``after``, or None."""
        with self._cond:
            fresh = self._cond.wait_for(
                lambda: self._time > after, timeout=FRAME_TIMEOUT_S if timeout is None else timeout
            )
            return (self._frame, self._time) if fresh else None


grabber = FrameGrabber()


@asynccontextmanager
async def lifespan(app: FastAPI):
    grabber.start()
    try:
        yield
    finally:
        grabber.stop()


app = FastAPI(lifespan=lifespan)


def encode_jpeg(frame) -> bytes:
    _, buffer = cv2.imencode(".jpg", frame)
    return buffer.tobytes()


def generate_frames():
    if grabber.running:
        last = time.monotonic()
        while True:
            got = grabber.next_frame(after=last)
            if got is None:
                break
            frame, last = got
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encode_jpeg(frame) + b"\r\n"
    else:  # no grabber (e.g. app used without its lifespan): read the camera directly
        while True:
            success, frame = read_frame()
            if not success:
                break
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encode_jpeg(frame) + b"\r\n"


@app.get("/")
def root():
    return {
        "message": "Webcam Service is Running",
        "version": "",
        "uptime": "",
        "routes": ["/", "/health", "/snapshot", "/video_feed"],
        "resolution": camera_info(),
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/snapshot")
def snapshot():
    """One JPEG frame, captured after this request arrived."""
    requested = time.monotonic()
    got = grabber.next_frame(after=requested)
    if got is None:
        raise HTTPException(
            status_code=503,
            detail="No camera frame: the camera can't be read (unplugged, or in use by another app).",
        )
    frame, read_time = got
    return Response(
        content=encode_jpeg(frame),
        media_type="image/jpeg",
        headers={"X-Frame-Delay-Ms": f"{(read_time - requested) * 1000:.0f}"},
    )


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001, help="Port to run the server on")
    parser.add_argument(
        "--log-file", help="Append stdout and stderr to this file instead of the console"
    )
    parser.add_argument("--width", type=int, default=REQUESTED_SIZE[0], help="Requested frame width")
    parser.add_argument("--height", type=int, default=REQUESTED_SIZE[1], help="Requested frame height")
    args = parser.parse_args()

    if (args.width, args.height) != REQUESTED_SIZE:
        REQUESTED_SIZE = (args.width, args.height)
        with cap_lock:
            cap.release()
            cap = open_camera()

    # Under pythonw.exe (used by the scheduled task) there is no console and
    # sys.stdout/sys.stderr are None, which crashes uvicorn's logging setup.
    if args.log_file:
        log = open(args.log_file, "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = log

    uvicorn.run(app, host="0.0.0.0", port=args.port)
