import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Импорты из твоих модулей
from responses import get_auto_reply
from utils.sheets import append_ticket, update_status
from utils.stats import generate_daily_report

# === Настройки ===
TOKEN = os.environ.get("TOKEN")
MODERATOR_CHAT_ID_ENV = os.environ.get("MODERATOR_CHAT_ID")
MODERATOR_CHAT_ID = int(MODERATOR_CHAT_ID_ENV) if MODERATOR_CHAT_ID_ENV else None
TOPICS_FILE = "topics.json"

# === Загрузка топиков ===
if os.path.exists(TOPICS_FILE):
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
        TOPICS = {k.strip().lower().replace(" ", "_"): v for k, v in raw.items()}
else:
    TOPICS = {}

# === Команды бота ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — оставьте ваше сообщение!"
    )

async def settopics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not MODERATOR_CHAT_ID or update.effective_chat.id != MODERATOR_CHAT_ID:
        return

    if not update.message.message_thread_id:
        await update.message.reply_text("⚠️ Команду нужно отправить внутри топика.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /settopics <название>")
        return

    name = context.args[0].strip().lower().replace(" ", "_")
    TOPICS[name] = update.message.message_thread_id

    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(TOPICS, f, ensure_ascii=False, indent=2)

    await update.message.reply_text(f'✅ Топик "{name}" сохранён. ID: {TOPICS[name]}')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or update.message.text.startswith("/"):
        return

    user = update.message.from_user
    user_id = user.id
    username = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
    user_message = update.message.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row_index = append_ticket(user_id, username, user_message, timestamp)
    auto_reply = get_auto_reply(user_message)

    # Кнопки действий
    keyboard = [[
        InlineKeyboardButton("🛠 В работу", callback_data=f"status:в работу:{row_index}:{user_id}"),
        InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{row_index}"),
        InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
        InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем оригинальное сообщение в топик "Новые"
    thread_id = TOPICS.get("новые")
    original_text = (
        f"📬 Новое обращение от @{username}\n\n"
        f"{user_message}\n\n"
        f"🕒 {timestamp}"
    )

    if thread_id and MODERATOR_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=MODERATOR_CHAT_ID,
                message_thread_id=thread_id,
                text=original_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"[ERROR] Не удалось отправить в топик 'Новые': {e}")

    # Отвечаем пользователю
    await update.message.reply_text(auto_reply)

# === Обработка нажатий на кнопки ===

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        data = query.data
        if data.startswith("status:"):
            parts = data.split(":")
            status = parts[1]
            row_index = int(parts[2])
            user_id = parts[3] if len(parts) > 3 else None

            # Обновляем статус в таблице
            update_status(row_index, status)

            # Получаем текст исходного сообщения
            original_text = query.message.text or ""

            # Формируем ключ топика
            target_topic_key = status.strip().lower().replace(" ", "_")
            thread_id = TOPICS.get(target_topic_key)

            if thread_id and MODERATOR_CHAT_ID:
                # Добавляем информацию о статусе
                new_text = f"{original_text}\n\n📌 Статус: {status}"

                # Создаём новую клавиатуру
                keyboard = [[
                    InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Отправляем в новый топик
                await context.bot.send_message(
                    chat_id=MODERATOR_CHAT_ID,
                    message_thread_id=thread_id,
                    text=new_text,
                    reply_markup=reply_markup
                )

            # Удаляем старое сообщение
            try:
                await query.message.delete()
            except Exception as e:
                print(f"[WARNING] Не удалось удалить сообщение: {e}")

        elif data.startswith("replyto:"):
            user_id = data.split(":")[1]
            await query.message.reply_text(f"/reply {user_id} ")

    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {e}")

# === Другие команды ===

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        report_text = generate_daily_report()
        thread_id = TOPICS.get("отчеты")
        if thread_id and MODERATOR_CHAT_ID:
            await context.bot.send_message(
                chat_id=MODERATOR_CHAT_ID,
                message_thread_id=thread_id,
                text=report_text
            )
        else:
            await update.message.reply_text(report_text)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при формировании отчёта: {e}")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("Использование: /reply <user_id> <сообщение>")
            return
        user_id = int(args[0])
        text = " ".join(args[1:])
        await context.bot.send_message(chat_id=user_id, text=text)
        await update.message.reply_text("✅ Ответ отправлен.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# === Запуск бота ===

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CommandHandler("settopics", settopics))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Очистка предыдущих обновлений
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))

    print("🚀 Бот запущен...")
    app.run_polling()
