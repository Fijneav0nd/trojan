"""
╔══════════════════════════════════════════════════╗
║         RELAY SERVER  —  relay_server.py         ║
║  Run this on your VPS / home server at port 8000 ║
║  pip install flask flask-socketio eventlet       ║
╚══════════════════════════════════════════════════╝
"""

import os
import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = "relay-secret-change-me"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet", ping_timeout=60)

PASSWORD = os.environ.get("RC_PASSWORD", "changeme123")  # set env var in prod

# Track connected agents (PC clients)
agents = {}          # agent_id -> sid
browser_clients = {} # sid -> agent_id

# ── Static UI ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/static/<path:path>")
def static_files(path):
    return send_from_directory("static", path)

# ── REST: auth ────────────────────────────────────────────────────────────────
@app.route("/api/auth", methods=["POST"])
def auth():
    data = request.json or {}
    if data.get("password") == PASSWORD:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Wrong password"}), 401

@app.route("/api/agents")
def list_agents():
    return jsonify({"agents": list(agents.keys())})

# ── SocketIO: Agent (PC) events ───────────────────────────────────────────────
@socketio.on("agent_register")
def agent_register(data):
    agent_id = data.get("agent_id", "default")
    secret   = data.get("secret", "")
    if secret != PASSWORD:
        emit("error", {"msg": "Bad secret"})
        return
    agents[agent_id] = request.sid
    join_room(f"agent_{agent_id}")
    print(f"[+] Agent registered: {agent_id} ({request.sid})")
    emit("registered", {"agent_id": agent_id})
    # notify browsers
    socketio.emit("agent_online", {"agent_id": agent_id}, room=f"browsers")

@socketio.on("agent_response")
def agent_response(data):
    """PC sends response back → forward to requesting browser"""
    target_sid = data.pop("_browser_sid", None)
    if target_sid:
        socketio.emit("cmd_response", data, room=target_sid)

@socketio.on("agent_screenshot")
def agent_screenshot(data):
    target_sid = data.pop("_browser_sid", None)
    if target_sid:
        socketio.emit("screenshot_data", data, room=target_sid)

@socketio.on("agent_webcam")
def agent_webcam(data):
    # broadcast webcam frame to all browsers watching this agent
    agent_id = data.get("agent_id", "default")
    socketio.emit("webcam_frame", data, room=f"browsers_watch_{agent_id}")

@socketio.on("agent_file_chunk")
def agent_file_chunk(data):
    target_sid = data.pop("_browser_sid", None)
    if target_sid:
        socketio.emit("file_chunk", data, room=target_sid)

# ── SocketIO: Browser (user) events ──────────────────────────────────────────
@socketio.on("browser_join")
def browser_join(data):
    if data.get("password") != PASSWORD:
        emit("error", {"msg": "Wrong password"})
        return
    join_room("browsers")
    agent_id = data.get("agent_id", "default")
    browser_clients[request.sid] = agent_id
    join_room(f"browsers_watch_{agent_id}")
    emit("joined", {"ok": True, "agents": list(agents.keys())})
    print(f"[+] Browser joined: {request.sid}")

@socketio.on("run_cmd")
def run_cmd(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if not agent_sid:
        emit("cmd_response", {"error": "Agent offline", "output": "", "code": -1})
        return
    data["_browser_sid"] = request.sid
    socketio.emit("run_cmd", data, room=agent_sid)

@socketio.on("request_screenshot")
def request_screenshot(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if not agent_sid:
        emit("error", {"msg": "Agent offline"})
        return
    socketio.emit("take_screenshot", {"_browser_sid": request.sid}, room=agent_sid)

@socketio.on("mouse_action")
def mouse_action(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        socketio.emit("mouse_action", data, room=agent_sid)

@socketio.on("key_action")
def key_action(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        socketio.emit("key_action", data, room=agent_sid)

@socketio.on("request_webcam")
def request_webcam(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        socketio.emit("start_webcam", {"_browser_sid": request.sid}, room=agent_sid)

@socketio.on("stop_webcam")
def stop_webcam(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        socketio.emit("stop_webcam", {}, room=agent_sid)

@socketio.on("upload_file")
def upload_file(data):
    """Browser sends base64 file → relay to agent"""
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        socketio.emit("save_file", data, room=agent_sid)
    else:
        emit("error", {"msg": "Agent offline"})

@socketio.on("request_file")
def request_file(data):
    agent_id = browser_clients.get(request.sid, "default")
    agent_sid = agents.get(agent_id)
    if agent_sid:
        data["_browser_sid"] = request.sid
        socketio.emit("send_file", data, room=agent_sid)

# ── Disconnect cleanup ────────────────────────────────────────────────────────
@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    # remove agent
    for aid, asid in list(agents.items()):
        if asid == sid:
            del agents[aid]
            socketio.emit("agent_offline", {"agent_id": aid}, room="browsers")
            print(f"[-] Agent disconnected: {aid}")
    # remove browser
    browser_clients.pop(sid, None)

if __name__ == "__main__":
    print("╔══════════════════════════════════════╗")
    print("║  Remote Control Relay Server         ║")
    print(f"║  Listening on  http://0.0.0.0:8000   ║")
    print(f"║  Password: {PASSWORD:<26}║")
    print("╚══════════════════════════════════════╝")
    socketio.run(app, host="0.0.0.0", port=8000, debug=False)
