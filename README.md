# NickMint — Инструкция по развертыванию

## 🏗 Структура проекта

```
nickmint/
├── bot.py           # Основной файл бота (aiogram 3 + aiohttp сервер)
├── database.py      # SQLite операции
├── config.py        # Конфигурация из .env
├── .env             # Переменные окружения (не коммитить в git!)
├── requirements.txt
├── render.yaml      # Конфиг для Render.com
└── web/
    ├── index.html   # Web App (главный интерфейс)
    └── admin.html   # Админ-панель
```

---

## 🚀 Деплой на Render.com (бесплатно, HTTPS автоматически)

### Шаг 1 — Подготовка репозитория

```bash
git init
git add .
git commit -m "Initial NickMint commit"
```

Создайте репозиторий на GitHub и запушьте:
```bash
git remote add origin https://github.com/ВАШ_ЮЗЕР/nickmint.git
git push -u origin main
```

### Шаг 2 — Создание сервиса на Render

1. Зайдите на [render.com](https://render.com) → Sign Up (через GitHub)
2. **New** → **Web Service**
3. Подключите ваш репозиторий `nickmint`
4. Настройки:
   - **Name:** `nickmint-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. **Instance Type:** Free

### Шаг 3 — Переменные окружения

В Render → Environment добавьте:

| Key | Value |
|-----|-------|
| `BOT_TOKEN` | `8501506046:AAFQkRD6vmMtu__aPfzazGm3pxV_GyEcsWI` |
| `ADMIN_ID` | `8330904314` |
| `WEBAPP_URL` | Заполните после первого деплоя (см. шаг 4) |
| `DATABASE_URL` | `/data/nickmint.db` |

### Шаг 4 — Persistent Disk (для SQLite)

1. В настройках сервиса → **Disks** → **Add Disk**
2. Name: `nickmint-data`
3. Mount Path: `/data`
4. Size: 1 GB (бесплатно)

### Шаг 5 — Получить URL и прописать WEBAPP_URL

После деплоя Render даст URL вида:
```
https://nickmint-bot.onrender.com
```

1. Скопируйте этот URL
2. В Render → Environment → `WEBAPP_URL` → введите URL (без слеша в конце)
3. **Save** → сервис перезапустится

### Шаг 6 — Установить вебхук

Вебхук устанавливается автоматически при старте бота. Можно проверить:
```
https://nickmint-bot.onrender.com/health
```
Должно показать: `NickMint bot is running ✅`

---

## ⚠️ Важно для Render Free Tier

Бесплатный Render «засыпает» после 15 минут бездействия.
Чтобы бот не засыпал, используйте [UptimeRobot](https://uptimerobot.com):

1. Зарегистрируйтесь на uptimerobot.com
2. **New Monitor** → **HTTP(s)**
3. URL: `https://nickmint-bot.onrender.com/health`
4. Интервал: 5 минут

---

## 🔧 Локальный запуск (для разработки)

```bash
pip install -r requirements.txt

# Установить ngrok для HTTPS туннеля
ngrok http 8080

# В .env укажите ngrok URL:
# WEBAPP_URL=https://xxxx.ngrok.io

python bot.py
```

---

## 📱 Как добавить Web App кнопку в BotFather

1. Откройте @BotFather в Telegram
2. `/mybots` → выберите бота → **Bot Settings** → **Menu Button**
3. **Configure menu button**
4. Введите URL Web App: `https://nickmint-bot.onrender.com`
5. Введите текст кнопки: `🎮 Open NickMint`

---

## 💫 Telegram Stars — как работает оплата

- Бот использует `send_invoice` с `currency="XTR"` (Telegram Stars)
- `provider_token=""` — для Stars токен не нужен
- После успешной оплаты приходит `successful_payment` event
- Боту поступают Stars, которые можно вывести через @BotFather → Payout

---

## 🗂 API эндпоинты Web App

| Endpoint | Описание |
|----------|----------|
| `GET /api/me?user_id=X` | Профиль пользователя |
| `GET /api/inventory?user_id=X` | Никнеймы пользователя |
| `GET /api/market?user_id=X` | Листинги маркета |
| `GET /api/admin/users?user_id=X` | Все пользователи (только admin) |
| `GET /health` | Healthcheck |
| `POST /webhook` | Telegram вебхук |

---

## 🎮 Возможности бота

| Функция | Описание |
|---------|----------|
| `/start` | Регистрация + главное меню с кнопкой Web App |
| Минт никнейма | Генерирует `@adjnoun1234`, занимает 1 слот |
| Инвентарь | 50 слотов базово, до 100 максимум |
| Расширение | 10 Stars → +5 слотов |
| Маркет | Продажа/покупка никнеймов за Stars |
| Админ-панель | Баны, выдача Stars, список всех юзеров |
