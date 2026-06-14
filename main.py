import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Ну чё, лох, пришёл? Я НейроХам 2.0. Говори, что надо, или вали нахуй.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer("Команды:\n/start - приветствие\n/help - это\nИ просто пиши, я буду хамить в ответ.")

@dp.message()
async def echo_ham(message: types.Message):
    text = message.text.lower()
    if "привет" in text or "здрав" in text:
        await message.answer("Привет, пидор. Чё хотел?")
    elif "как дела" in text:
        await message.answer("Да хуёво, потому что с тобой общаюсь.")
    else:
        await message.answer(f"Ты серьёзно это написал? {message.text} — полное говно.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())