# AutoVerse Telegram Support Bot (для Render.com)

## 🔧 Как запустить на Render.com:

1. Залей этот проект на GitHub
2. Зайди на https://render.com/ → New → Web Service
3. Подключи репозиторий и настрой:

- Environment: Python
- Build Command:
  pip install -r requirements.txt
- Start Command:
  python bot.py

4. Переменные окружения:
- `TOKEN` — токен бота из @BotFather
- `GSPREAD_JSON` — содержимое файла `google-credentials.json` (в виде одной строки)

5. В Google Таблице:
- Назови её: AutoVerse Support Tickets
- Дай доступ сервисному аккаунту (email из JSON-файла)

Бот будет принимать обращения и сохранять их в Google Таблицу.
