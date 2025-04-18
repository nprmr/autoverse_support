import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

from responses import get_auto_reply
from utils.sheets import append_ticket, update_status
from utils.stats import generate_daily_report

TOKEN = os.environ.get("TOKEN")
MODERATOR_CHAT_ID = int(os.environ.get("MODERATOR_CHAT_ID"))
TOPICS_FILE = "topics.json"

if os.path.exists(TOPICS_FILE):
    with open(TOPICS_FILE, "r") as f:
        raw = json.load(f)
        TOPICS = {k.strip().lower().replace(" ", "_"): v for k, v in raw.items()}
else:
    TOPICS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — оставьте ваше сообщение!"
    )

async def settopics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat_id != MODERATOR_CHAT_ID:
        return
    if not update.message.is_topic_message:
        await update.message.reply_text("⚠️ Команду нужно отправить внутри топика.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /settopics <название>")
        return
    name = context.args[0].strip().lower().replace(" ", "_")
    TOPICS[name] = update.message.message_thread_id
    with open(TOPICS_FILE, "w") as f:
        json.dump(TOPICS, f)
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
    await update.message.reply_text(auto_reply)

    print("👤 user_id =", user_id)
    print("🔘 callback_data =", f"status:в работу:{row_index}:{user_id}")
    keyboard = [
        [
            InlineKeyboardButton("🛠 В работу", callback_data=f"status:в работу:{row_index}:{user_id}"),
            InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{row_index}"),
            InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
            InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    thread_id = TOPICS.get("новые")
    print("📩 Новый тикет, топик 'новые':", thread_id)
    if thread_id:
        await context.bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            message_thread_id=thread_id,
            text=f"<pre>📬 Новое обращение от @{username}\n\n{user_message}\n\n🕒 {timestamp}</pre>",
            parse_mode="HTML",
            reply_markup=reply_markup
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('✅ Кнопка нажата')
    # query уже объявлен выше
    print('📦 query.data =', query.data)
    # query уже объявлен выше
    await query.answer()
    try:
        data = query.data
        if data.startswith("status:"):
            parts = data.split(":")
            status = parts[1]
            row_index = int(parts[2])
            user_id = parts[3] if len(parts) > 3 else None
            update_status(row_index, status)

            try:
                await query.message.delete()
            except:
                pass

            key = status.strip().lower().replace(" ", "_")
            thread_id = TOPICS.get(key)
            print("🔁 Переносим тикет, статус:", status)
            print("🧵 TOPICS:", TOPICS)
            print("📍 Используем ключ:", key)

            if thread_id:
                text = f"📌 Обращение #{row_index}\nСтатус: {status}"
                print("👤 user_id =", user_id)
    print("🔘 callback_data =", f"status:в работу:{row_index}:{user_id}")
    keyboard = [[InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")]]
                await context.bot.send_message(
                    chat_id=MODERATOR_CHAT_ID,
                    message_thread_id=thread_id,
                    text=text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        elif data.startswith("replyto:"):
            user_id = data.split(":")[1]
            await query.message.reply_text(f"/reply {user_id} ")
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {e}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        report = generate_daily_report()
        thread_id = TOPICS.get("отчеты")
        if thread_id:
            await context.bot.send_message(chat_id=MODERATOR_CHAT_ID, message_thread_id=thread_id, text=report)
        else:
            await update.message.reply_text(report)
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

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    import asyncio
    asyncio.get_event_loop().run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CommandHandler("settopics", settopics))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.run_polling()
