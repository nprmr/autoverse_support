import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

# Получаем токен из переменной окружения
TOKEN = os.environ.get("TOKEN")

# Получаем ключ Google Sheets из переменной окружения и подгружаем его как dict
gspread_key = json.loads(os.environ.get("GSPREAD_JSON"))

# Авторизация Google Sheets
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(gspread_key, scope)
client = gspread.authorize(creds)

# Название таблицы
sheet = client.open("AutoVerse Support Tickets").sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — "
        "оставьте ваше сообщение!"
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
    user_message = update.message.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Добавляем строку в Google Таблицу
    sheet.append_row([str(user_id), username, user_message, timestamp])

    # Ответ пользователю
    await update.message.reply_text("Мы получили ваше обращение и свяжемся с вами в ближайшее время!")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен...")
    app.run_polling()
