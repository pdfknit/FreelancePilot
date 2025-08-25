# telegram_bot/main.py
import os, sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from telegram_bot.config import BOT_TOKEN
    from telegram_bot.api_client import post_chat_message
else:
    from .config import BOT_TOKEN
    from .api_client import post_chat_message

import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command


async def handle_any_text(message: Message):
    text = message.text or ""
    try:
        data = await post_chat_message(message.from_user.id, text, message.from_user.username)
        reply = data.get("reply") or data.get("message") or "Ок."
        actions = data.get("actions") or []

        kb = None
        if actions:
            rows = []
            for a in actions:
                if a.get("type") == "tg_inline":
                    rows.append([InlineKeyboardButton(text=a["text"], callback_data=a["callback"])])
            if rows:
                kb = InlineKeyboardMarkup(inline_keyboard=rows)

        await message.answer(reply, reply_markup=kb)
    except Exception:
        await message.answer("Сервер недоступен. Попробуй позже.")


async def on_startup(bot: Bot):
    me = await bot.get_me()
    print(f"Bot @{me.username} started")


async def handle_start(message: Message):
    # /start [optional_payload]
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        # просто приветствие (без аргумента)
        await message.answer(
            "Привет! Я помогу оценивать задачи и трекать время.\n"
            "Команды: /rate 25, /add <текст>, /estimate <id>, /start <id>, /stop, /report week"
        )
        return

    arg = parts[1].strip()

    import re
    m = re.search(r"(\d+)", arg)
    if not m:
        await message.answer("Не вижу ID задачи. Пример: /start 42")
        return

    task_id = m.group(1)
    try:
        data = await post_chat_message(message.from_user.id, f"start {task_id}", message.from_user.username)
        reply = data.get("reply") or data.get("message") or f"Старт трекинга по задаче {task_id}"
        await message.answer(reply)
    except Exception:
        await message.answer("Не получилось стартовать таймер. Проверь доступность сервера.")


async def handle_any_text(message: Message):
    text = message.text or ""
    try:
        data = await post_chat_message(message.from_user.id, text, message.from_user.username)
        reply = data.get("reply") or data.get("message") or "Ок."
        actions = data.get("actions") or []

        kb = None
        if actions:
            rows = []
            for a in actions:
                if a.get("type") == "tg_inline":
                    rows.append([InlineKeyboardButton(text=a["text"], callback_data=a["callback"])])
            if rows:
                kb = InlineKeyboardMarkup(inline_keyboard=rows)

        await message.answer(reply, reply_markup=kb)
    except Exception:
        await message.answer("Сервер недоступен. Попробуй позже.")


async def handle_start_timer(message: Message):
    # /start_timer <task_id>  → на сервер отправляем "start <task_id>"
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 1:
        await message.answer("Использование: /start_timer <task_id>")
        return
    task_id = parts[1].strip()
    try:
        data = await post_chat_message(message.from_user.id, f"start {task_id}", message.from_user.username)
        reply = data.get("reply") or data.get("message") or f"Старт трекинга по задаче {task_id}"
        await message.answer(reply)
    except Exception:
        await message.answer("Не удалось стартовать таймер. Сервер недоступен?")


async def handle_stop_timer(message: Message):
    # /stop_timer  → на сервер отправляем "stop"
    try:
        data = await post_chat_message(message.from_user.id, "stop", message.from_user.username)
        reply = data.get("reply") or data.get("message") or "Таймер остановлен."
        await message.answer(reply)
    except Exception:
        await message.answer("Не удалось остановить таймер. Сервер недоступен?")


async def handle_cb(cb: CallbackQuery):
    data = cb.data or ""
    parts = data.split("|", 2)  # ожидаем confirm|<id>|<action>
    if len(parts) != 3 or parts[0] != "confirm":
        await cb.answer()
        return
    est_id, action = parts[1], parts[2]

    # Шлём как обычное сообщение в тот же API:
    resp = await post_chat_message(cb.from_user.id, f"confirm {est_id} {action}", cb.from_user.username)
    await cb.answer("Готово")
    await cb.message.answer(resp.get("reply") or "Ок")


def main():
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан или выглядит неверно. Проверь .env/переменные окружения.")
    dp = Dispatcher()
    bot = Bot(BOT_TOKEN, parse_mode=None)
    dp.startup.register(on_startup)
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_start_timer, Command("start_timer"))
    dp.message.register(handle_stop_timer, Command("stop_timer"))
    dp.callback_query.register(handle_cb)
    for cmd in ("rate", "add", "estimate", "stop", "report"):
        dp.message.register(handle_any_text, Command(cmd))

    dp.message.register(handle_any_text, F.text)
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
