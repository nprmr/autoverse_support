import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

from responses import get_auto_reply

TOKEN = os.environ.get("TOKEN")
gspread_key = json.loads(os.environ.get("GSPREAD_JSON"))
MODERATOR_CHAT_ID = os.environ.get("MODERATOR_CHAT_ID")

scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_dict(gspread_key, scope)
client = gspread.authorize(creds)

sheet = client.open("AutoVerse Support Tickets").sheet1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = (
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — "
        "оставьте ваше сообщение!"
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
    user_message = update.message.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Сохраняем в таблицу
    sheet.append_row([str(user_id), username, user_message, timestamp])

    # Отвечаем пользователю
    auto_reply = get_auto_reply(user_message)
    await update.message.reply_text(auto_reply)

    # Уведомляем модератора
    if MODERATOR_CHAT_ID:
        message = (
            f"<pre>📬 Новое обращение от @{username or 'пользователя'}

"
            f"{user_message}

🕒 {timestamp}</pre>"
        )
        await context.bot.send_message(chat_id=int(MODERATOR_CHAT_ID), text=message, parse_mode="HTML")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
