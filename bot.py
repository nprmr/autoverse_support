import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from utils.sheets import append_ticket
from responses import get_auto_reply
import os

TOKEN = os.getenv("TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # ID вашей группы

TOPIC_NEW = 120
TOPIC_WORK = 124
TOPIC_DONE = 128
TOPIC_REJECTED = 132

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здравствуйте! Напишите, с чем вам нужна помощь — мы ответим как можно скорее.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    # Проверка на команду 'reply'
    if message.text.startswith("reply"):
        parts = message.text.split(maxsplit=2)
        if len(parts) >= 3:
            target_user_id = int(parts[1])
            reply_text = parts[2]
            try:
                await context.bot.send_message(chat_id=target_user_id, text=reply_text)
                await message.reply_text("✅ Ответ отправлен пользователю!")
            except Exception as e:
                await message.reply_text(f"❌ Ошибка при отправке: {e}")
        else:
            await message.reply_text("❗ Неверный формат команды. Пример: reply 123456789 Ваш ответ")
        return
    user_message = message.text
    username = message.from_user.username or "(не указано)"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    user_id = message.from_user.id

    # Сохраняем тикет в Google Sheets
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_ticket(full_name, username, user_message, timestamp)

    # Ответ пользователю
    await message.reply_text("✅ Ваше сообщение принято! Спасибо, что обратились.")

    # Автоответ по смыслу
    auto_reply = get_auto_reply(user_message)
    await message.reply_text(auto_reply)

    # Отправка тикета в топик "Новые" с кнопками "В работу" и "Отклонить"
    keyboard = [
        [
            InlineKeyboardButton("🛠 В работу", callback_data=f"work:{user_id}:{user_message}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{user_id}:{user_message}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=TOPIC_NEW,
        text=f"📩 Новое обращение от @{username} (ID {user_id}):\n\n{user_message}",
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    action = data[0]
    user_id = data[1]
    user_message = data[2] if len(data) > 2 else None

    if action == "work":
        # Перенос в "В работе" с новыми кнопками
        keyboard = [
            [
                InlineKeyboardButton("✉ Ответить", callback_data=f"reply:{user_id}"),
                InlineKeyboardButton("✅ Закрыть", callback_data=f"close:{user_id}:{user_message}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_WORK,
           text=f"🛠 В работе: от ID {user_id}:\n\n{user_message}",

            reply_markup=reply_markup
        )

        await query.edit_message_text("✅ Переведено в работу")

    elif action == "reject":
        # Перенос в "Отклоненные"
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_REJECTED,
            text=f"❌ Отклонено: от ID {user_id}:\n\n{user_message}",

        )
        await query.edit_message_text("❌ Отклонено")

    elif action == "reply":
        # Подготовить маску ответа
        await query.message.reply_text(f"reply {user_id} Ваш ответ...")

    elif action == "close":
        # Перенос в "Завершенные"
        await context.bot.send_message(
            chat_id=GROUP_ID,
            message_thread_id=TOPIC_DONE,


async def on_startup(app):
    await app.bot.delete_webhook(drop_pending_updates=True)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()
