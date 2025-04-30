import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from utils.sheets import append_ticket
from responses import get_auto_reply
import os

TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))  # ID вашей группы

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

    # Если мы находимся в пользовательском топике — пересылаем в ЛС
    if message.message_thread_id:
        for uid, thread_id in context.bot_data.get("user_topics", {}).items():
            if thread_id == message.message_thread_id:
                try:
                    await context.bot.send_message(chat_id=uid, text=message.text)
                    await message.reply_text("✅ Ответ отправлен пользователю из их топика")
                except Exception as e:
                    await message.reply_text(f"❌ Ошибка при отправке: {e}")
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

    # Ответ пользователю (один автоответ, только если не в работе)
    if user_id not in context.bot_data.get("user_topics", {}):
        auto_reply = get_auto_reply(user_message)
        default_reply = "✅ Спасибо за сообщение! Мы всё передадим команде поддержки."
        if auto_reply != default_reply:
            await message.reply_text(auto_reply)
        else:
            await message.reply_text(default_reply)

    # Отправка тикета в топик "Новые" с кнопками "В работу" и "Отклонить"
    keyboard = [
        [
            InlineKeyboardButton("🛠 В работу", callback_data=f"work:{user_id}:{user_message}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{user_id}:{user_message}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

            # Если есть персональный топик — направим туда
    thread_id = context.bot_data.get("user_topics", {}).get(user_id, TOPIC_NEW)

    await context.bot.send_message(
        chat_id=GROUP_ID,
        message_thread_id=thread_id,
        text=f"📩 Новое обращение от @{username} (ID {user_id}):\n\n{user_message}",
        reply_markup=reply_markup if thread_id == TOPIC_NEW else None
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    action = data[0]
    user_id = data[1]
    user_message = data[2] if len(data) > 2 else None

    # Инициализация хранилища, если не существует
    if "user_topics" not in context.bot_data:
        context.bot_data["user_topics"] = {}

    if action == "work":
        # Создаём топик для пользователя, если ещё не создан
        if int(user_id) not in context.bot_data["user_topics"]:
            username = query.from_user.username or "(не указано)"
            topic = await context.bot.create_forum_topic(
                chat_id=GROUP_ID,
                name=f"Обращение от {user_id}"
            )
            context.bot_data["user_topics"][int(user_id)] = topic.message_thread_id

            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic.message_thread_id,
                text=f"📩 Сообщение от пользователя, в работе у @{username} (ID {user_id}):\n\n{user_message}"
            )

            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=topic.message_thread_id,
                text="🛠 Используйте команду /close в этом топике для его завершения."
            )

        thread_id = context.bot_data["user_topics"][int(user_id)]

        # Уведомление пользователя о переводе в работу
        await context.bot.send_message(
            chat_id=int(user_id),
            text="👨‍💻 Ваше обращение принято в работу. Ожидайте ответа от оператора."
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
            text=f"✅ Завершено: от ID {user_id}:\n\n{user_message}"

        )

        # Закрытие пользовательского топика, если он есть
        if "user_topics" in context.bot_data:
            thread_id = context.bot_data["user_topics"].get(int(user_id))
            if thread_id:
                try:
                    await context.bot.close_forum_topic(
                        chat_id=GROUP_ID,
                        message_thread_id=thread_id
                    )
                    del context.bot_data["user_topics"][int(user_id)]
                except Exception as e:
                    await query.message.reply_text(f"⚠️ Не удалось закрыть топик: {e}")

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Ваше обращение закрыто. Спасибо, что обратились!"
        )

        await query.edit_message_text("✅ Завершено")

async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    thread_id = update.message.message_thread_id
    if not thread_id:
        await update.message.reply_text("❗ Команду /close можно использовать только внутри форумного топика.")
        return

    user_topics = context.bot_data.get("user_topics", {})
    for uid, tid in user_topics.items():
        if tid == thread_id:
            await context.bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=TOPIC_DONE,
                text=f"✅ Завершено: от ID {uid}:\n\n(закрыто вручную через /close)"
            )
            await context.bot.close_forum_topic(chat_id=GROUP_ID, message_thread_id=thread_id)
            del context.bot_data["user_topics"][uid]
            await update.message.reply_text("✅ Топик закрыт. Пользователь уведомлён.")
            await context.bot.send_message(chat_id=uid, text="✅ Ваше обращение закрыто. Спасибо, что обратились!")
            return

    await update.message.reply_text("❗ Этот топик не зарегистрирован как персональный. Закрытие невозможно.")


from telegram import BotCommand

async def on_startup(app):
    await app.bot.delete_webhook(drop_pending_updates=True)

    await app.bot.set_my_commands([
        BotCommand("close", "Закрыть обращение (внутри персонального топика)")
    ])

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("close", close_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()
