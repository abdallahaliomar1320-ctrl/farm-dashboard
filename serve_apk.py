import http.server
import socketserver
import socket
import os

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

ip = get_ip()
PORT = 8081
# Path to the apk
apk_dir = os.path.join("mobile_app", "build", "app", "outputs", "flutter-apk")

# Make sure directory exists, else fallback to current
if not os.path.exists(apk_dir):
    print("APK directory not found, serving current dir")
    apk_dir = "."

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=apk_dir, **kwargs)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://{ip}:{PORT}")
    httpd.serve_forever()
