import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

from responses import get_auto_reply
from utils.sheets import append_ticket, update_status

TOKEN = os.environ.get("TOKEN")
MODERATOR_CHAT_ID = os.environ.get("MODERATOR_CHAT_ID")

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

    # Добавляем тикет в таблицу и получаем номер строки
    row_index = append_ticket(user_id, username, user_message, timestamp)

    # Ответ пользователю
    auto_reply = get_auto_reply(user_message)
    await update.message.reply_text(auto_reply)

    # Кнопки для модератора
    keyboard = [
        [
            InlineKeyboardButton("🛠 В работу", callback_data=f"status:в работу:{row_index}"),
            InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{row_index}"),
            InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем уведомление модератору
    if MODERATOR_CHAT_ID:
        message = (
            f"<pre>📬 Новое обращение от @{username or 'пользователя'}\n\n"
            f"{user_message}\n\n🕒 {timestamp}</pre>"
        )
        await context.bot.send_message(
            chat_id=int(MODERATOR_CHAT_ID),
            text=message,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, status, row = query.data.split(":")
        update_status(int(row), status)
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(f"✅ Статус обновлён: {status}")
    except Exception as e:
        await query.message.reply_text(f"Ошибка при обновлении статуса: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
