# 🖥️ tg_remote

Повне дистанційне керування ПК через Telegram бота.
Один бот — необмежена кількість комп'ютерів через хмарний роутер на Railway.

---

## ⚡ Можливості

- 📸 Скріншот екрану
- 📷 Фото з вебкамери
- 📊 Моніторинг CPU / RAM / диску / процесів
- 💻 Виконання команд у терміналі
- 🌐 Відкриття сайтів у браузері
- 🔊 Керування гучністю
- 🔒 Блокування екрану
- ⚡ Вимкнення / перезавантаження / сплячий режим
- 🖥️ Підтримка кількох ПК одночасно через один бот

---

## 🏗️ Архітектура

```
Telegram → Railway (server.py) → tg_home.exe
                               → tg_work.exe
                               → tg_friend.exe
```

Сервер отримує команди від бота і роздає їх по черзі кожному ПК.
Конфліктів між ПК немає — кожен читає тільки свою чергу.

---

## 📁 Структура проекту

```
📁 tg_remote
├── tg.py              ← клієнт (запускається на кожному ПК)
├── patch.py           ← вшиває налаштування в tg.py
├── setup.bat          ← автоматичне налаштування і збірка exe
├── server.py          ← сервер-роутер (деплоїться на Railway)
├── requirements.txt   ← залежності для сервера
├── railway.json       ← конфіг для Railway
└── Procfile           ← команда запуску для Railway
```

---

## 🚀 Швидкий старт

### 1. Створи Telegram бота

- Відкрий **@BotFather** → `/newbot`
- Скопіюй `BOT_TOKEN`
- Відкрий **@userinfobot** → скопіюй свій `CHAT_ID`

### 2. Задеплой сервер на Railway

1. Зареєструйся на [railway.app](https://railway.app)
2. Створи новий проект → **Deploy from GitHub**
3. Завантаж `server.py`, `requirements.txt`, `railway.json` у репо
4. Додай змінні середовища:
   ```
   BOT_TOKEN = твій_токен
   CHAT_ID   = твій_chat_id
   ```
5. У **Settings → Networking → Generate Domain** вкажи порт `8080`
6. Скопіюй отриманий URL (наприклад `https://server-xxx.up.railway.app`)

### 3. Встанови вебхук

Відкрий в браузері:
```
https://api.telegram.org/botТВІЙ_ТОКЕН/setWebhook?url=https://ТВІЙ_URL.railway.app/webhook
```

### 4. Збери exe для ПК

У терміналі:
```bash
python patch.py "ТОКЕН" "CHAT_ID" "home" "https://ТВІЙ_URL.railway.app"
python -m PyInstaller --onefile --noconsole --name "tg_home" tg_build.py
```

### 5. Запусти

Запусти `dist\tg_home.exe` — в Telegram прийде повідомлення:
```
home online - 14:23:01
```

---

## 📋 Команди бота

| Команда | Опис |
|---|---|
| `/pcs` | Які ПК онлайн |
| `/screenshot home` | Скріншот екрану |
| `/webcam home` | Фото з вебкамери |
| `/sysinfo home` | CPU, RAM, диск, процеси |
| `/volume_up home` | Гучність +10% |
| `/volume_down home` | Гучність -10% |
| `/mute home` | Вимкнути/увімкнути звук |
| `/run home ipconfig` | Виконати команду в терміналі |
| `/open home google.com` | Відкрити сайт у браузері |
| `/lock home` | Заблокувати екран |
| `/sleep home` | Сплячий режим |
| `/restart home` | Перезавантаження через 5 сек |
| `/shutdown home` | Вимкнення через 5 сек |
| `/stop home` | Зупинити скрипт |

> Замість `home` підстав назву свого ПК.
> Використай `all` замість імені щоб виконати команду на всіх ПК одразу.

---

## 🖥️ Для кількох ПК

Для кожного нового ПК збери окремий exe з унікальною назвою:

```bash
python patch.py "ТОКЕН" "CHAT_ID" "friend" "https://ТВІЙ_URL.railway.app"
python -m PyInstaller --onefile --noconsole --name "tg_friend" tg_build.py
```

Скинь `tg_friend.exe` другу — він просто запускає і все.
Python встановлювати не потрібно.

---

## ⚙️ Вимоги

- **ОС**: Windows 10 / 11
- **Python**: 3.10+ (тільки для збірки exe)
- **Інтернет**: потрібен на кожному ПК

### Залежності

```
opencv-python
pyautogui
Pillow
requests
psutil
pyinstaller
```

Встановити одразу:
```bash
pip install opencv-python pyautogui Pillow requests psutil pyinstaller
```

---

## 📝 Ліцензія

MIT — використовуй як хочеш.
