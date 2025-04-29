import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from sheets import append_ticket
from responses import get_response
import os

TOKEN = os.getenv("TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Здравствуйте! Напишите, с чем вам нужна помощь — мы ответим как можно скорее.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = message.chat_id

    # Получение текста и данных пользователя
    user_message = message.text
    username = message.from_user.username or "(не указано)"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    # Сохраняем тикет в Google Sheets
    append_ticket([full_name, username, user_message])

    # Ответ пользователю
    await message.reply_text("✅ Ваше сообщение принято! Спасибо, что обратились.")

    # Оповещение админа (если нужно, можно вставить ID админа)
    # await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="Новый тикет от пользователя...")

    # Подготовка клавиатуры для операторов
    keyboard = [[
        InlineKeyboardButton("📝 Начать обработку", callback_data=f"status:v_rabote:{message.message_id}:{chat_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    ticket_text = (
        f"📩 Сообщение от пользователя:\n"
        f"{message.text}\n"
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split(":")
    if data[0] == "status" and data[1] == "v_rabote":
        original_message_id = int(data[2])
        user_chat_id = int(data[3])

        await context.bot.send_message(
            chat_id=user_chat_id,
            text="👨‍💻 Оператор начал обрабатывать ваше обращение. Ожидайте ответа."
        )

        await query.edit_message_text("📝 Статус: В обработке")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()
