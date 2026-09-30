import os
import time
import subprocess
import datetime
import threading
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)
OUTPUT_FOLDER = "webhook_screenshots"
CAPTURE_INTERVAL = 2  # How often to capture if in "loop" mode
MAX_FILES = 20

def ensure_folder():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

def cleanup_old_files():
    files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('.png')]
    if len(files) > MAX_FILES:
        files.sort()
        for f in files[:len(files) - MAX_FILES]:
            os.remove(os.path.join(OUTPUT_FOLDER, f))

def capture_screenshot(filename=None):
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.png"
    full_path = os.path.join(OUTPUT_FOLDER, filename)
    
    try:
        subprocess.run([
            "termux-screenshot",
            "-f", full_path
        ], check=True, timeout=5)
        return full_path
    except Exception as e:
        return f"Error: {e}"

@app.route('/capture', methods=['GET', 'POST'])
def handle_capture():
    """
    Trigger a screenshot.
    Access via: http://<YOUR_IP>:5000/capture
    """
    filename = request.args.get('name', None)
    result = capture_screenshot(filename)
    print(f"[!] Capture triggered: {result}")
    return jsonify({"status": "success", "file": result})

@app.route('/loop', methods=['POST'])
def toggle_loop():
    """
    Start or stop a continuous capture loop.
    Send: {"action": "start"} or {"action": "stop"}
    """
    global capture_loop
    data = request.get_json() or {}
    action = data.get('action')
    
    if action == 'start':
        if not capture_loop.is_alive():
            capture_loop.start()
            return jsonify({"status": "started", "interval": CAPTURE_INTERVAL})
        else:
            return jsonify({"status": "already_running"})
    elif action == 'stop':
        capture_loop.stop()
        return jsonify({"status": "stopped"})

class CaptureLoop(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        ensure_folder()
        print(f"[*] Loop started (interval: {CAPTURE_INTERVAL}s)")
        while self.running:
            capture_screenshot()
            cleanup_old_files()
            time.sleep(CAPTURE_INTERVAL)
        print("[-] Loop stopped")

    def stop(self):
        self.running = False

# Initialize the background loop thread
capture_loop = CaptureLoop()

if __name__ == '__main__':
    ensure_folder()
    print("[*] Starting Webhook Server on port 5000")
    print("[*] To trigger a capture, visit: http://<YOUR_IP>:5000/capture")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
