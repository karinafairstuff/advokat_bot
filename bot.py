import os
import time
from datetime import datetime

import telebot
from telebot import types

# --- Конфигурация ---

# На Render токен берём из переменной окружения BOT_TOKEN
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Админы, которым отправляем заявки (мама и ты)
ADMIN_CHAT_IDS = [
    738258564,     # мама
    2110398264    # ты
]

bot = telebot.TeleBot(BOT_TOKEN)

# Храним временные сессии для /consult:
# { chat_id: {"collecting": bool, "messages": [Message, ...]} }
user_sessions = {}

# Текст кнопок
BTN_SEND = "✅ Отправить заявку"
BTN_MORE = "❌ Ещё не всё"


# ---------- Вспомогательные функции ----------

def get_consult_keyboard() -> types.ReplyKeyboardMarkup:
    """Клавиатура для этапа подтверждения заявки."""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton(BTN_SEND))
    kb.add(types.KeyboardButton(BTN_MORE))
    return kb


def clear_session(chat_id: int):
    """Удалить временную сессию пользователя."""
    if chat_id in user_sessions:
        del user_sessions[chat_id]


def send_pretty_admin_copy(message: telebot.types.Message, from_session: bool = False):
    """
    Отправляет админам красивое структурированное сообщение
    + оригинал сообщения клиента (forward).
    """
    user = message.from_user
    full_name = (
        f"{user.first_name or ''} {user.last_name or ''}".strip() or "Не указано"
    )
    username = f"@{user.username}" if user.username else "нет username"
    chat_id = message.chat.id

    # Определяем тип и превью
    if message.content_type == "text":
        msg_type = "Текст"
        preview = message.text or ""
    elif message.content_type == "photo":
        msg_type = "Фото"
        preview = "(фотография)"
    elif message.content_type == "document":
        msg_type = f"Документ: {message.document.file_name}"
        preview = "(документ)"
    else:
        msg_type = message.content_type
        preview = "(сообщение)"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    source = "через /consult" if from_session else "обычное сообщение"

    admin_text = (
        "🆕 *Новая заявка от клиента*\n\n"
        f"📥 *Источник:* {source}\n\n"
        f"👤 *Имя:* {full_name}\n"
        f"🔗 *Username:* {username}\n"
        f"🆔 *Chat ID:* `{chat_id}`\n"
        f"⏰ *Время:* {timestamp}\n"
        f"📎 *Тип:* {msg_type}\n\n"
        f"💬 *Сообщение:*\n> {preview}"
    )

    for admin_id in ADMIN_CHAT_IDS:
        try:
            # сначала — структурированная карточка
            bot.send_message(admin_id, admin_text, parse_mode="Markdown")
            # потом — оригинальное сообщение (текст/фото/документ)
            bot.forward_message(admin_id, message.chat.id, message.message_id)
        except Exception as e:
            print(f"Ошибка отправки сообщения admin_id={admin_id}: {e}")


# ---------- Команда /start ----------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    text = (
        "Здравствуйте! 👋\n"
        "Я ассистент адвоката.\n\n"
        "Вы можете:\n"
        "• Написать вопрос в свободной форме\n"
        "• Использовать команду /consult, чтобы пошагово оформить заявку\n"
        "• Посмотреть справку через /help\n\n"
        "Все сообщения передаются адвокату конфиденциально."
    )
    bot.reply_to(message, text)


# ---------- Команда /help ----------

@bot.message_handler(commands=['help'])
def send_help(message):
    text = (
        "ℹ️ *Помощь*\n\n"
        "Я помогу вам оформить обращение к адвокату.\n\n"
        "Рекомендуемый порядок:\n"
        "1️⃣ Нажмите /consult\n"
        "2️⃣ Напишите одно или несколько сообщений с:\n"
        "   • вашим именем\n"
        "   • контактом для связи\n"
        "   • описанием ситуации\n"
        "   • удобным временем для связи\n"
        f"3️⃣ Когда напишете всё, нажмите кнопку «{BTN_SEND}».\n\n"
        f"До нажатия этой кнопки ваши сообщения *не отправляются* адвокату."
    )
    bot.reply_to(message, text, parse_mode="Markdown")


# ---------- Команда /consult ----------

@bot.message_handler(commands=['consult'])
def consult_info(message):
    chat_id = message.chat.id

    # создаём/обновляем сессию
    user_sessions[chat_id] = {
        "collecting": True,
        "messages": []
    }

    text = (
        "📝 *Запись на консультацию*\n\n"
        "Пожалуйста, напишите одно или несколько сообщений с:\n"
        "1️⃣ Вашим именем\n"
        "2️⃣ Контактом для связи (телефон, Telegram или e-mail)\n"
        "3️⃣ Кратким описанием вашей ситуации\n"
        "4️⃣ Удобным временем для связи\n\n"
        f"Когда напишете всё, нажмите кнопку «{BTN_SEND}».\n"
        f"Если хотите дописать ещё, используйте «{BTN_MORE}»."
    )

    bot.send_message(
        chat_id,
        text,
        parse_mode="Markdown",
        reply_markup=get_consult_keyboard()
    )


# ---------- Обработка кнопок подтверждения ----------

@bot.message_handler(func=lambda m: m.text in [BTN_SEND, BTN_MORE], content_types=['text'])
def handle_confirm_buttons(message):
    chat_id = message.chat.id
    text = message.text
    session = user_sessions.get(chat_id)

    # Кнопка "Ещё не всё"
    if text == BTN_MORE:
        bot.reply_to(
            message,
            "Хорошо 👍\nНапишите всё, что считаете важным.\n"
            f"Когда будете готовы — нажмите «{BTN_SEND}»."
        )
        return

    # Кнопка "Отправить заявку"
    if text == BTN_SEND:
        if not session or not session.get("messages"):
            bot.reply_to(
                message,
                "Пока у меня нет информации для заявки.\n"
                "Пожалуйста, сначала напишите сообщение с описанием вашей ситуации, "
                f"а затем снова нажмите «{BTN_SEND}»."
            )
            return

        # Пересылаем ВСЕ накопленные сообщения админам
        for stored_msg in session["messages"]:
            send_pretty_admin_copy(stored_msg, from_session=True)

        # Благодарность клиенту
        bot.send_message(
            chat_id,
            "Спасибо! 🙏\nВаша заявка отправлена адвокату. "
            "С вами свяжутся после ознакомления.",
            reply_markup=types.ReplyKeyboardRemove()
        )

        # очищаем сессию
        clear_session(chat_id)
        return


# ---------- Общий обработчик сообщений ----------

@bot.message_handler(content_types=['text', 'photo', 'document'])
def handle_any_message(message):
    chat_id = message.chat.id

    # 1. Игнорируем команды (/start, /help, /consult и т.п.)
    if message.content_type == "text" and message.text.startswith("/"):
        return

    session = user_sessions.get(chat_id)

    # 2. Если пользователь в режиме оформления заявки (/consult),
    #    просто копим сообщения, не пересылаем и не отвечаем.
    if session and session.get("collecting"):
        session["messages"].append(message)
        return

    # 3. Обычный сценарий (человек просто пишет без /consult):
    #    сразу отправляем красивую карточку + оригинал админам
    #    и благодарим клиента.
    send_pretty_admin_copy(message, from_session=False)

    bot.reply_to(
        message,
        "Спасибо! 🙏\nВаше сообщение получено и передано адвокату. "
        "С вами свяжутся после ознакомления."
    )


print("Бот запущен...")

# Надёжный polling с автоперезапуском
while True:
    try:
        bot.infinity_polling(timeout=30, long_polling_timeout=25)
    except Exception as e:
        print(f"Ошибка в polling: {e}")
        print("Перезапуск через 3 секунды...")
        time.sleep(3)
