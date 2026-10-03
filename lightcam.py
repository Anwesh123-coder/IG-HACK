import http.server
import socketserver
import threading
import subprocess
import time
import sys
import socket

PORT = 8080
# Use 'auto' to let ffmpeg pick the default, or specify '0' for front, '1' for rear
# On Termux, you often need to specify the device explicitly if multiple exist
DEVICE = "0" 
WIDTH = 640
HEIGHT = 480
FPS = 30

class MJPEGHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>Termux LightCam</title>
            <style>
                body { background: #000; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
                img { max-width: 100%; max-height: 100%; object-fit: contain; }
            </style>
            </head>
            <body>
                <img src="/stream" alt="Live Feed">
            </body>
            </html>
            """
            self.wfile.write(html.encode())
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            # Start ffmpeg stream
            # -f avfoundation is for Mac, but on Termux/Android, we use the standard input
            # We use 'auto' or specific device index. 
            # Note: Termux's ffmpeg uses the standard V4L2-like interface or Android MediaCodec backend.
            cmd = [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-f', 'v4l2', # On Termux, this maps to Android's camera interface
                '-i', f'/dev/video{DEVICE}', # Often /dev/video0 is front, /dev/video1 is rear. 
                # If that fails, try -list_devices to find the exact path.
                '-r', str(FPS),
                '-s', f'{WIDTH}x{HEIGHT}',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-qscale:v', '5', # High quality, low size
                '-an', # No audio
                'pipe:1'
            ]
            
            # Fallback: If /dev/videoX doesn't work, try the default input
            if not self._check_ffmpeg(cmd):
                 cmd[cmd.index('/dev/video0')] = 'auto' 
                 if not self._check_ffmpeg(cmd):
                     self.wfile.write(b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera initialization failed. Check device index.\r\n')
                     return

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            try:
                while True:
                    # Read a JPEG frame. JPEGs start with FF D8 and end with FF D9
                    # We use a simple buffer approach
                    header = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                    
                    # Read until we find the end of JPEG marker
                    # This is a simplified read. For production, use a proper JPEG parser.
                    # However, for MJPEG, we can just read chunks and send.
                    # Better approach: Read a fixed size or detect boundary.
                    # Since ffmpeg outputs raw JPEG stream, we need to detect boundaries.
                    
                    # Simple boundary detection: Look for FFD9
                    # We'll read 4096 bytes at a time
                    buf = b''
                    while not buf.endswith(b'\xff\xd9'):
                        chunk = process.stdout.read(4096)
                        if not chunk:
                            break
                        buf += chunk
                    
                    if not buf:
                        break
                        
                    self.wfile.write(header + buf + b'\r\n')
                    self.wfile.flush()
                    
            except BrokenPipeError:
                pass
            except Exception as e:
                print(f"Stream error: {e}", file=sys.stderr)
            finally:
                process.terminate()
                process.wait()

    def _check_ffmpeg(self, cmd):
        try:
            # Quick test to see if the command starts
            p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=2)
            return p.returncode == 0 or p.returncode == -15 # -15 is SIGTERM, which is expected if we killed it
        except subprocess.TimeoutExpired:
            return True # It's running, which is good
        except Exception:
            return False

    def log_message(self, format, *args):
        # Suppress default logging to keep console clean
        pass

class ReusableTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8"))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    ip = get_local_ip()
    print(f"LightCam running at http://{ip}:{PORT}")
    print(f"Stream URL: http://{ip}:{PORT}/stream")
    print("Press Ctrl+C to stop.")
    
    try:
        server = ReusableTCPServer(('0.0.0.0', PORT), MJPEGHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
