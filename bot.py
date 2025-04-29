import os
import sys
import json
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# === Защита от дублирования инстансов ===
LOCK_FILE = ".bot.lock"

if os.path.exists(LOCK_FILE):
    os.remove(LOCK_FILE)
    print("🧹 Старый lock-файл удален")

with open(LOCK_FILE, "w") as f:
    f.write("")
print("✅ Lock-файл создан")

import atexit

def remove_lock_file():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)
        print("🧹 Lock-файл удалён")

atexit.register(remove_lock_file)

# === Настройки бота ===
TOKEN = os.environ.get("TOKEN")
MODERATOR_CHAT_ID_ENV = os.environ.get("MODERATOR_CHAT_ID")
MODERATOR_CHAT_ID = int(MODERATOR_CHAT_ID_ENV) if MODERATOR_CHAT_ID_ENV else None
TOPICS_FILE = "topics.json"

if os.path.exists(TOPICS_FILE):
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        raw_topics = json.load(f)
        TOPICS = {k.strip().lower().replace(" ", "_"): v for k, v in raw_topics.items()}
else:
    TOPICS = {}

try:
    from responses import get_auto_reply
    from utils.sheets import append_ticket, update_status
    from utils.stats import generate_daily_report
except ImportError as e:
    print(f"[ERROR] Не удалось импортировать модули: {e}")
    sys.exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет, мы команда службы поддержки AutoVerse. "
        "Если вы столкнулись с проблемой или хотите предложить улучшения нашего продукта — оставьте ваше сообщение!"
    )

async def settopics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not MODERATOR_CHAT_ID or update.effective_chat.id != MODERATOR_CHAT_ID:
        return
    if not update.message.message_thread_id:
        await update.message.reply_text("⚠️ Команду нужно выполнить внутри топика.")
        return
    if len(context.args) != 1:
        await update.message.reply_text("Использование: /settopics <название>")
        return
    name = context.args[0].strip().lower().replace(" ", "_")
    TOPICS[name] = update.message.message_thread_id
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in TOPICS.items()}, f, ensure_ascii=False, indent=2)
    await update.message.reply_text(f"📌 Топик '{name}' зарегистрирован с ID потока: {update.message.message_thread_id}")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if MODERATOR_CHAT_ID and update.effective_chat.id != MODERATOR_CHAT_ID:
        return
    try:
        daily_report = generate_daily_report()
        await update.message.reply_text(daily_report)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при формировании отчёта: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    message = update.message
    chat_id = message.chat_id
    auto_response = get_auto_reply(message.text)
    if auto_response:
        await message.reply_text(auto_response)
        return
    if not MODERATOR_CHAT_ID:
        await message.reply_text("❌ MODERATOR_CHAT_ID не задан")
        return
    try:
        thread_id = TOPICS.get("novye") or 1
        keyboard = [[
            InlineKeyboardButton("📝 Начать обработку", callback_data=f"status:v_rabote:{message.message_id}:{chat_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        ticket_text = (
            f"📩 Сообщение от пользователя:
"
            f"{message.text}

"
            f"🆔 ID пользователя: {chat_id}
"
            f"🕒 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        sent_message = await context.bot.send_message(
            chat_id=MODERATOR_CHAT_ID,
            message_thread_id=thread_id,
            text=ticket_text,
            reply_markup=reply_markup
        )
        append_ticket(sent_message.message_id, chat_id, message.text, "новый")
    except Exception as e:
        print(f"[ERROR] При обработке входящего сообщения: {e}")

async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Использование: /reply <user_id> <message_id> <сообщение>")
            return
        user_id = int(args[0])
        original_message_id = int(args[1])
        text = " ".join(args[2:])
        await context.bot.send_message(chat_id=user_id, text=text)
        await update.message.reply_text("✅ Ответ отправлен.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при выполнении /reply: {e}")
        print(f"[ERROR] При выполнении /reply: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        data = query.data
        if data.startswith("status:"):
            parts = data.split(":")
            status = parts[1]
            message_id = int(parts[2])
            user_id = parts[3] if len(parts) > 3 else None
            update_status(message_id, status)
            target_topic_key = status.strip().lower().replace(" ", "_")
            thread_id = TOPICS.get(target_topic_key)
            if not MODERATOR_CHAT_ID:
                await query.message.reply_text("❌ MODERATOR_CHAT_ID не задан")
                return
            if not thread_id:
                await query.message.reply_text(f"❌ Не найден топик '{target_topic_key}'. Зарегистрируйте его через /settopics")
                return
            base_text = query.message.text.split("📌")[0].strip()
            new_text = f"{base_text}

📌 Статус: {status}"
            keyboard = [[
                InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}:{message_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=MODERATOR_CHAT_ID,
                message_thread_id=thread_id,
                text=new_text,
                reply_markup=reply_markup
            )
            try:
                await query.message.delete()
            except Exception as e:
                print(f"[WARNING] Не удалось удалить сообщение: {e}")
        elif data.startswith("replyto:"):
            parts = data.split(":")
            if len(parts) < 3:
                await query.message.reply_text("⚠️ Неверный формат данных кнопки.")
                return
            user_id = parts[1]
            original_message_id = parts[2]
            await query.message.reply_text(f"/reply {user_id} {original_message_id} ")
    except Exception as e:
        await query.message.reply_text(f"❌ Ошибка: {e}")
        print(f"[ERROR] При обработке кнопки: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("reply", reply))
    app.add_handler(CommandHandler("settopics", settopics))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Бот успешно запущен...")
    app.run_polling()
