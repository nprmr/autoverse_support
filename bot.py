import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

from responses import get_auto_reply
from utils.sheets import append_ticket, update_status
from utils.stats import generate_daily_report

TOKEN = os.environ.get("TOKEN")
MODERATOR_CHAT_ID = int(os.environ.get("MODERATOR_CHAT_ID"))
TOPICS_FILE = "topics.json"

# Загружаем сохранённые топики
if os.path.exists(TOPICS_FILE):
    with open(TOPICS_FILE, "r") as f:
        raw_topics = json.load(f)
    TOPICS = {k.strip().lower().replace(' ', '_'): v for k, v in raw_topics.items()}
else:
    TOPICS = {}

async def settopics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.chat_id != MODERATOR_CHAT_ID:
        return
    if not update.message.is_topic_message:
        await update.message.reply_text("⚠️ Команду нужно отправить внутри топика.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /settopics <название>")
        return
    name = context.args[0].lower()
    key = name.strip().lower().replace(" ", "_")
    TOPICS[key] = update.message.message_thread_id
    with open(TOPICS_FILE, "w") as f:
        json.dump(TOPICS, f)
    await update.message.reply_text(f'✅ Топик "{name}" сохранён. ID: {TOPICS[name]}')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — оставьте ваше сообщение!"
    )

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

    keyboard = [[
        InlineKeyboardButton("🛠 В работу", callback_data=f"status:в работу:{row_index}:{user_id}"),
        InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{row_index}"),
        InlineKeyboardButton("❌ Отклонено", callback_data=f"status:отклонено:{row_index}"),
        InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    thread_id = TOPICS.get("новые")
    print("➡️ Отправляем тикет в топик новые:", thread_id)
    if thread_id:
        msg = f"<pre>📬 Новое обращение от @{username or 'пользователя'}\n\n{user_message}\n\n🕒 {timestamp}</pre>"
        await context.bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            message_thread_id=thread_id,
            text=msg,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("⚠️ Топик 'новые' не настроен. Отправь /settopics новые в нужный топик.")

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

            update_status(row_index, status)

            try:
                await query.message.delete()
            except:
                pass

            key = status.strip().lower().replace(" ", "_")
            print("🔁 Переносим тикет")
            print("СТАТУС:", status)
            print("TOPICS:", TOPICS)
            print("Ищем ключ:", key)
            thread_id = TOPICS.get(key)
            print("STATUS:", key, "| THREAD_ID:", thread_id, "| TOPICS:", TOPICS)
            if thread_id:
                text = f"📌 Обращение #{row_index}\nСтатус: {status}"
                keyboard = [[
                    InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}")
                ]]
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
        await query.message.reply_text(f"Ошибка при обработке кнопки: {e}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        report = generate_daily_report()
        thread_id = TOPICS.get("отчеты")
        print("📊 Отчет пойдет в топик:", thread_id)
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
            await update.message.reply_text("Usage: /reply <user_id> <message>")
            return
        user_id = int(args[0])
        text = " ".join(args[1:])
        await context.bot.send_message(chat_id=user_id, text=text)
        await update.message.reply_text("✅ Message sent.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

import asyncio


        app = ApplicationBuilder().token(TOKEN).build()
    import asyncio
    asyncio.get_event_loop().run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))

    import asyncio
    import asyncio
    asyncio.get_event_loop().run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))

        app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CommandHandler("settopics", settopics))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT, handle_message))

        app.run_polling()

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
