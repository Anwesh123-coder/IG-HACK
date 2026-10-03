import cv2
import threading
import time
from flask import Flask, Response, render_template_string

app = Flask(__name__)

# --- Configuration ---
CAMERA_INDEX = 0  # 0 for front/selfie, 1 for rear (varies by OS/device)
WIDTH = 640       # 640x480 is a good balance for mobile bandwidth
HEIGHT = 480
FPS = 30
JPEG_QUALITY = 85 # Balance between quality and file size

# --- Global State ---
frame = None
frame_lock = threading.Lock()
stream_active = False

class CameraStream:
    """
    Handles camera capture in a dedicated thread to ensure 
    the web server remains responsive.
    """
    def __init__(self, source=CAMERA_INDEX, width=WIDTH, height=HEIGHT):
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera index {source}")
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, FPS)
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        """Continuously reads frames from the camera."""
        global frame
        while self.running:
            ret, current_frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            # Apply mirror effect for selfie camera (optional but standard)
            if CAMERA_INDEX == 0:
                current_frame = cv2.flip(current_frame, 1)
                
            # Update global frame with lock
            with frame_lock:
                frame = current_frame

    def release(self):
        """Cleanup resources."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        self.cap.release()

# Initialize Camera
try:
    cam = CameraStream()
except Exception as e:
    print(f"Camera initialization error: {e}")
    raise

def generate_frames():
    """
    Generator for MJPEG stream.
    Yields JPEG-encoded bytes in the correct multipart format.
    """
    while True:
        with frame_lock:
            if frame is None:
                time.sleep(0.01)
                continue
            # Encode frame to JPEG
            ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
            if not ret:
                continue
                
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')

# --- Web Routes ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartCam</title>
    <style>
        body { 
            margin: 0; 
            background: #1a1a1a; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            font-family: sans-serif;
        }
        .container {
            max-width: 100%;
            text-align: center;
        }
        h1 { color: #fff; margin-bottom: 10px; font-size: 1.5rem; }
        img { 
            max-width: 100%; 
            border-radius: 12px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.5); 
            border: 2px solid #444;
        }
        .status { color: #0f0; font-size: 0.9rem; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Live Selfie View</h1>
        <img src="/stream" alt="Live Camera Feed">
        <div class="status">Connected</div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream')
def stream():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snapshot')
def snapshot():
    """Returns a single high-res JPEG snapshot."""
    with frame_lock:
        if frame is None:
            return "No frame available", 503
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return Response(jpeg.tobytes(), mimetype='image/jpeg')

if __name__ == '__main__':
    import socket
    
    # Get local IP to display in console
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8"))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "127.0.0.1"
        
    print(f"SmartCam running at http://{ip}:5000")
    print(f"Stream URL: http://{ip}:5000/stream")
    print(f"Snapshot URL: http://{ip}:5000/snapshot")
    
    try:
        # threaded=True allows multiple clients to view simultaneously
        app.run(host='0.0.0.0', port=5000, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        cam.release()
