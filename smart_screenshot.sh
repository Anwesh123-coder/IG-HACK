#!/data/data/com.termux/files/usr/bin/bash

# 1. SETUP
PORT=5000
OUTPUT_DIR="screenshot_tmp"
mkdir -p $OUTPUT_DIR

# Ensure Termux:API is installed
if ! command -v termux-screenshot &> /dev/null; then
    echo "Error: termux-screenshot not found. Please run: pkg install termux-api"
    exit 1
fi

# 2. THE FLASK APP (Embedded)
cat << 'EOF' > app.py
import os
import subprocess
import datetime
import requests
from flask import Flask, redirect, send_file

app = Flask(__name__)
OUTPUT_DIR = "screenshot_tmp"

@app.route('/')
def capture_and_redirect():
    # 1. Generate a unique filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"shot_{timestamp}.png"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    # 2. Take Screenshot
    try:
        subprocess.run(["termux-screenshot", "-f", filepath], check=True, timeout=5)
    except Exception as e:
        return f"Error capturing screen: {e}"

    # 3. Upload to public paste site (0x0.st)
    try:
        with open(filepath, 'rb') as f:
            r = requests.post('https://0x0.st', files={'file': f}, timeout=30)
        public_url = r.text.strip()
        
        # 4. Clean up local file
        os.remove(filepath)
        
        # 5. Redirect to the public URL
        return redirect(public_url)
    except Exception as e:
        return f"Upload failed: {e}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
EOF

echo "[+] Setup complete. Starting server on port $PORT..."
python app.py
