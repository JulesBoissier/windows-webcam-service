import argparse
import sys
import threading

import cv2
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
cap = cv2.VideoCapture(0)  # Open webcam
cap_lock = threading.Lock()  # VideoCapture is not thread-safe across requests


def read_frame():
    global cap
    with cap_lock:
        if not cap.isOpened():
            # Camera was unplugged or grabbed by another app; try to reopen it
            cap.release()
            cap = cv2.VideoCapture(0)
        return cap.read()


def generate_frames():
    while True:
        success, frame = read_frame()
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", frame)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buffer.tobytes() + b"\r\n"
            )

@app.get("/")
def root():
    return {
        "message": "Webcam Service is Running",
        "version": "",
        "uptime": "",
        "routes": ["/", "/health", "/video_feed"],
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001, help="Port to run the server on")
    parser.add_argument(
        "--log-file", help="Append stdout and stderr to this file instead of the console"
    )
    args = parser.parse_args()

    # Under pythonw.exe (used by the scheduled task) there is no console and
    # sys.stdout/sys.stderr are None, which crashes uvicorn's logging setup.
    if args.log_file:
        log = open(args.log_file, "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = log

    uvicorn.run(app, host="0.0.0.0", port=args.port)
