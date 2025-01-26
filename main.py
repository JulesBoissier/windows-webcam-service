import cv2
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
cap = cv2.VideoCapture(0)  # Open webcam

def generate_frames():
    while True:
        success, frame = cap.read()
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
    return {"message": "Webcam Service Running"}

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
