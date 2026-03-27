# ╔══════════════════════════════════════════════════════╗
# ║           REMOTE CONTROL — SETUP GUIDE              ║
# ╚══════════════════════════════════════════════════════╝

## 📁 File Structure

    remote-control/
    ├── relay_server.py        ← runs on your VPS / server
    ├── pc_agent.py            ← runs on your Windows PC
    ├── static/
    │   └── index.html         ← web UI (served by relay server)
    ├── requirements_server.txt
    └── requirements_agent.txt

═══════════════════════════════════════════════════════

## 🖥️ STEP 1 — Set up the Relay Server (VPS or home server)

Install Python 3.9+ then:

    pip install -r requirements_server.txt

Edit relay_server.py and set your password:

    PASSWORD = "your-strong-password-here"

Run it:

    python relay_server.py

Your web UI is now at:  http://YOUR_SERVER_IP:8000

═══════════════════════════════════════════════════════

## 💻 STEP 2 — Set up the PC Agent (Windows PC to control)

Install Python 3.9+ then:

    pip install -r requirements_agent.txt

Edit pc_agent.py — set your server address and password:

    SERVER_URL = "http://YOUR_SERVER_IP:8000"
    PASSWORD   = "your-strong-password-here"
    AGENT_ID   = "my-pc"   # any name you like

Run it:

    python pc_agent.py

═══════════════════════════════════════════════════════

## 🌐 STEP 3 — Open the Web UI

Open your browser and go to:

    http://YOUR_SERVER_IP:8000

Enter the server address and password, then click Connect.

═══════════════════════════════════════════════════════

## 🔒 Security Tips

- Change PASSWORD from the default "changeme123"
- Put the relay server behind nginx + HTTPS (port 443)
- Only expose port 8000 (or better, use a reverse proxy)
- For extra security, add IP allowlisting in relay_server.py

═══════════════════════════════════════════════════════

## 🧩 Features

  ✅ Terminal  — run any Windows shell command remotely
  ✅ Screen    — screenshot + auto-refresh + mouse click control
  ✅ Webcam    — live webcam stream (~10 fps)
  ✅ Files     — upload files TO your PC / download FROM your PC
  ✅ Keyboard  — type text, hotkeys (Ctrl+C, Win+L, etc.), arrow keys

═══════════════════════════════════════════════════════

## ⚡ Auto-start on Windows (run agent at boot)

Create a .bat file:

    @echo off
    cd C:\path\to\remote-control
    python pc_agent.py

Then press Win+R → shell:startup → paste shortcut there.

Or use Task Scheduler to run it as a background service.
