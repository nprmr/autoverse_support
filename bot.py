import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

from responses import get_auto_reply
from utils.sheets import append_ticket, update_status
from utils.stats import generate_daily_report

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
    if not update.message or update.message.text is None:
        return

    if update.message.text.strip().startswith("/"):
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
    user_message = update.message.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row_index = append_ticket(user_id, username, user_message, timestamp)
    auto_reply = get_auto_reply(user_message)
    await update.message.reply_text(auto_reply)

    keyboard = [
        [
            InlineKeyboardButton("🛠 В работу", callback_data=f"status:в работу:{row_index}"),
            InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{row_index}"),
            InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
            InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if MODERATOR_CHAT_ID:
        message = f"<pre>📬 Новое обращение от @{username or 'пользователя'}\n\n{user_message}\n\n🕒 {timestamp}</pre>"
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
        if query.data.startswith("status:"):
            _, status, row = query.data.split(":")
            row_index = int(row)
            update_status(row_index, status)

            if status == "в работу":
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Завершено", callback_data=f"status:готово:{row_index}"),
                        InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
                    ]
                ]
                await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
                await query.message.reply_text("📌 Статус обновлён: в работу. Выберите финальный статус.")
            else:
                await query.edit_message_reply_markup(None)
                await query.message.reply_text(f"✅ Статус обновлён: {status}")

        elif query.data.startswith("replyto:"):
            user_id = query.data.split(":")[1]
            await query.message.reply_text(f"/reply {user_id} ")

    except Exception as e:
        await query.message.reply_text(f"Ошибка при обработке кнопки: {e}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        report = generate_daily_report()
        await update.message.reply_text(report)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при формировании отчёта: {e}")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Usage: /reply <user_id> <message>")
            return

        user_id = int(args[0])
        text = " ".join(args[1:])
        await context.bot.send_message(chat_id=user_id, text=text)
        await update.message.reply_text("✅ Message sent.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    import asyncio
    asyncio.get_event_loop().run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    app.run_polling()
