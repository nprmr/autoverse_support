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
    await update.message.reply_text("Бот работает. Напиши сообщение.")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"🆔 chat_id: `{chat_id}`", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Получено сообщение:", update)
    
    if not update.message:
        print("❗ update.message отсутствует")
        return

    try:
        user = update.message.from_user
        user_id = user.id
        username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
        user_message = update.message.text
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"От {username} ({user_id}): {user_message}")

        try:
            sheet.append_row([str(user_id), username, user_message, timestamp])
            print("✅ Сохранено в Google Таблицу")
        except Exception as e:
            print(f"❌ Ошибка при сохранении в таблицу: {e}")

        try:
            auto_reply = get_auto_reply(user_message)
            await update.message.reply_text(auto_reply)
        except Exception as e:
            print(f"❌ Ошибка при автоответе: {e}")

        if MODERATOR_CHAT_ID:
            try:
                message = (
                    f"📬 Новое обращение от @{username or 'пользователя'}\n\n"
                    f"{user_message}\n\n🕒 {timestamp}"
                )
                await context.bot.send_message(chat_id=int(MODERATOR_CHAT_ID), text=message)
                print("📤 Уведомление модератору отправлено")
            except Exception as e:
                print(f"❌ Ошибка при отправке уведомления модератору: {e}")

    except Exception as e:
        print(f"❌ Общая ошибка в обработке сообщения: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getid", get_chat_id))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    print("🟢 Бот запущен и готов к приёму сообщений")
    app.run_polling()
