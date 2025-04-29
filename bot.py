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
    print("❌ Бот уже запущен. Завершаю текущий процесс.")
    sys.exit(1)

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

# === Загрузка топиков из файла ===
if os.path.exists(TOPICS_FILE):
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        raw_topics = json.load(f)
        # Приводим все ключи к формату "в_работе"
        TOPICS = {k.strip().lower().replace(" ", "_"): v for k, v in raw_topics.items()}
else:
    TOPICS = {}

# === Импорты из твоих модулей ===
try:
    from responses import get_auto_reply
    from utils.sheets import append_ticket, update_status
    from utils.stats import generate_daily_report
except ImportError as e:
    print(f"[ERROR] Не удалось импортировать модули: {e}")
    sys.exit(1)

# === Команды ===
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

    with open(TOPICS_FILE, "w", encoding="utf-8") как обычно, но после ответа она должна меняться на «✅ В завершённые»

            elif data.startswith("replyto:"):
                parts = data.split(":")
                if len(parts) < 3:
                    await query.message.reply_text("⚠️ Неверный формат данных кнопки.")
                    return
                user_id = parts[1]
                original_message_id = parts[2]

                # Добавляем текст для отправки ответа
                await query.message.reply_text(f"/reply {user_id} {original_message_id} ")

        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")
            print(f"[ERROR] При обработке кнопки: {e}")

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

            # Отправляем ответ пользователю
            await context.bot.send_message(chat_id=user_id, text=text)

            # Проверяем, что мы в правильном чате
            if update.effective_chat.id != MODERATOR_CHAT_ID:
                await update.message.reply_text("⚠️ Эту команду можно использовать только в модераторском чате.")
                return

            # Получаем исходное сообщение с тикетом
            orig_message = await context.bot.get_message(
                chat_id=MODERATOR_CHAT_ID,
                message_id=original_message_id
            )

            original_text = orig_message.text or ""

            # Обновляем карточку, добавляя статус и новую кнопку "Готово"
            new_text = original_text.split("\n\n📌")[0] + f"\n\n📌 Статус: готово"

            thread_id = TOPICS.get("готово")
            if not thread_id:
                await update.message.reply_text("❌ Топик 'готово' не найден. Зарегистрируйте его через `/settopics готово`")
                return

            # Создаём новую клавиатуру
            keyboard = [[
                InlineKeyboardButton("✅ Готово", callback_data=f"status:готово:{original_message_id}:{user_id}")
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
                await orig_message.delete()
            except Exception as e:
                print(f"[WARNING] Не удалось удалить сообщение: {e}")

            await update.message.reply_text("✅ Сообщение отправлено пользователю и тикет перенесён в топик 'готово'.")

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка при выполнении /reply: {e}")
            print(f"[ERROR] При выполнении /reply: {e}")

    # === Обработка кнопок (статусы) ===
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

                # Обновляем статус в Google Sheets
                update_status(message_id, status)

                # Формируем ключ топика
                target_topic_key = status.strip().lower().replace(" ", "_")
                thread_id = TOPICS.get(target_topic_key)

                print(f"[DEBUG] Целевой топик: {target_topic_key}, ID: {thread_id}")

                if not MODERATOR_CHAT_ID:
                    await query.message.reply_text("❌ MODERATOR_CHAT_ID не задан")
                    return

                if not thread_id:
                    await query.message.reply_text(f"❌ Не найден топик '{target_topic_key}'. Зарегистрируйте его через /settopics")
                    return

                # Копируем текст сообщения
                original_text = query.message.text or ""
                new_text = f"{original_text.split('📌')[0]}\n\n📌 Статус: {status}"

                # Создаём новую разметку с кнопкой "Ответить"
                keyboard = [[
                    InlineKeyboardButton("📝 Ответить", callback_data=f"replyto:{user_id}:{message_id}")
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
                original_message_id = data.split(":")[2]
                await query.message.reply_text(f"/reply {user_id} {original_message_id} ")

        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка: {e}")
            print(f"[ERROR] При обработке кнопки: {e}")

    # === Запуск бота ===
    if __name__ == "__main__":
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("report", report))
        app.add_handler(CommandHandler("reply", reply))
        app.add_handler(CommandHandler("settopics", settopics))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Удаление вебхука при запуске
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(app.bot.delete_webhook(drop_pending_updates=True))

        print("🚀 Бот успешно запущен...")
        app.run_polling()
