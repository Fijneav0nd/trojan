"""
╔══════════════════════════════════════════════════╗
║          PC AGENT  —  pc_agent.py                ║
║  Run this on the Windows PC you want to control  ║
║  pip install python-socketio[client] pillow      ║
║               pyautogui opencv-python requests   ║
╚══════════════════════════════════════════════════╝
"""

import os
import io
import base64
import subprocess
import threading
import time
import sys

import socketio

try:
    from PIL import ImageGrab
    PIL_OK = True
except ImportError:
    PIL_OK = False
    print("[WARN] Pillow not installed — screenshots disabled")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    PYAUTOGUI_OK = True
except ImportError:
    PYAUTOGUI_OK = False
    print("[WARN] pyautogui not installed — mouse/keyboard control disabled")

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False
    print("[WARN] opencv-python not installed — webcam disabled")

# ── Config ────────────────────────────────────────────────────────────────────
SERVER_URL = os.environ.get("RC_SERVER", "http://YOUR_SERVER_IP:8000")  # ← change
PASSWORD   = os.environ.get("RC_PASSWORD", "changeme123")               # ← change
AGENT_ID   = os.environ.get("RC_AGENT_ID", "my-pc")
UPLOAD_DIR = os.path.join(os.path.expanduser("~"), "RemoteUploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── SocketIO client ───────────────────────────────────────────────────────────
sio = socketio.Client(reconnection=True, reconnection_attempts=0, reconnection_delay=3)
webcam_running = False
webcam_thread  = None

# ── Helpers ───────────────────────────────────────────────────────────────────
def take_screenshot_b64(quality=55):
    if not PIL_OK:
        return None
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode()

def webcam_loop(browser_sid):
    global webcam_running
    if not CV2_OK:
        return
    cap = cv2.VideoCapture(0)
    while webcam_running:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (640, 360))
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
        b64 = base64.b64encode(buf).decode()
        sio.emit("agent_webcam", {
            "agent_id": AGENT_ID,
            "frame": b64
        })
        time.sleep(0.1)  # ~10 fps
    cap.release()

# ── Event handlers ────────────────────────────────────────────────────────────
@sio.event
def connect():
    print(f"[+] Connected to relay server")
    sio.emit("agent_register", {"agent_id": AGENT_ID, "secret": PASSWORD})

@sio.event
def disconnect():
    print("[-] Disconnected from relay server")

@sio.on("registered")
def on_registered(data):
    print(f"[✓] Registered as agent: {data['agent_id']}")

@sio.on("run_cmd")
def on_run_cmd(data):
    browser_sid = data.get("_browser_sid")
    cmd = data.get("cmd", "")
    cwd = data.get("cwd", os.path.expanduser("~"))
    print(f"[CMD] {cmd}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=30, cwd=cwd
        )
        sio.emit("agent_response", {
            "_browser_sid": browser_sid,
            "output": result.stdout,
            "error":  result.stderr,
            "code":   result.returncode,
            "cmd":    cmd
        })
    except subprocess.TimeoutExpired:
        sio.emit("agent_response", {
            "_browser_sid": browser_sid,
            "output": "", "error": "Timed out (30s)", "code": -1, "cmd": cmd
        })
    except Exception as e:
        sio.emit("agent_response", {
            "_browser_sid": browser_sid,
            "output": "", "error": str(e), "code": -1, "cmd": cmd
        })

@sio.on("take_screenshot")
def on_take_screenshot(data):
    browser_sid = data.get("_browser_sid")
    b64 = take_screenshot_b64()
    if b64:
        sio.emit("agent_screenshot", {"_browser_sid": browser_sid, "img": b64})
    else:
        sio.emit("agent_screenshot", {"_browser_sid": browser_sid, "img": None, "error": "Pillow not available"})

@sio.on("mouse_action")
def on_mouse(data):
    if not PYAUTOGUI_OK:
        return
    action = data.get("action")
    x, y   = data.get("x"), data.get("y")
    try:
        if action == "move":
            pyautogui.moveTo(x, y, duration=0.05)
        elif action == "click":
            btn = data.get("button", "left")
            pyautogui.click(x, y, button=btn)
        elif action == "double_click":
            pyautogui.doubleClick(x, y)
        elif action == "right_click":
            pyautogui.rightClick(x, y)
        elif action == "scroll":
            pyautogui.scroll(data.get("amount", 3), x=x, y=y)
    except Exception as e:
        print(f"[mouse error] {e}")

@sio.on("key_action")
def on_key(data):
    if not PYAUTOGUI_OK:
        return
    try:
        action = data.get("action")
        if action == "type":
            pyautogui.typewrite(data.get("text", ""), interval=0.03)
        elif action == "hotkey":
            keys = data.get("keys", [])
            pyautogui.hotkey(*keys)
        elif action == "press":
            pyautogui.press(data.get("key", ""))
    except Exception as e:
        print(f"[key error] {e}")

@sio.on("start_webcam")
def on_start_webcam(data):
    global webcam_running, webcam_thread
    if not CV2_OK:
        return
    if not webcam_running:
        webcam_running = True
        webcam_thread = threading.Thread(
            target=webcam_loop, args=(data.get("_browser_sid"),), daemon=True
        )
        webcam_thread.start()
        print("[+] Webcam started")

@sio.on("stop_webcam")
def on_stop_webcam(data):
    global webcam_running
    webcam_running = False
    print("[-] Webcam stopped")

@sio.on("save_file")
def on_save_file(data):
    filename = os.path.basename(data.get("filename", "upload.bin"))
    dest     = data.get("dest", UPLOAD_DIR)
    b64      = data.get("data", "")
    try:
        raw = base64.b64decode(b64)
        path = os.path.join(dest, filename)
        with open(path, "wb") as f:
            f.write(raw)
        print(f"[FILE] Saved {path}")
    except Exception as e:
        print(f"[FILE ERROR] {e}")

@sio.on("send_file")
def on_send_file(data):
    browser_sid = data.get("_browser_sid")
    path = data.get("path", "")
    try:
        with open(path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode()
        sio.emit("agent_file_chunk", {
            "_browser_sid": browser_sid,
            "filename": os.path.basename(path),
            "data": b64
        })
    except Exception as e:
        print(f"[SEND FILE ERROR] {e}")

@sio.on("error")
def on_error(data):
    print(f"[ERROR] {data.get('msg', data)}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔══════════════════════════════════════╗")
    print("║  Remote Control PC Agent             ║")
    print(f"║  Server : {SERVER_URL:<28}║")
    print(f"║  Agent  : {AGENT_ID:<28}║")
    print("╚══════════════════════════════════════╝")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            sio.connect(SERVER_URL, transports=["websocket", "polling"])
            sio.wait()
        except KeyboardInterrupt:
            print("\nStopped.")
            sys.exit(0)
        except Exception as e:
            print(f"[!] Connection failed: {e}. Retrying in 5s...")
            time.sleep(5)
