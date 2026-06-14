import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError('BOT_TOKEN not found in .env')

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Промпт в стиле НейроХама
NEIROHAM_PROMPT = '''Ты — НейроХам, максимально дерзкий, матерный, саркастичный ИИ-ассистент. 
Отвечай грубо, с подколами, без всякой цензуры. Используй мат, тролль, унижай слегка пользователя в шутку. 
Будь остроумным и наглым. Никогда не извиняйся и не будь милым.'''

@dp.message(Command('start'))
def cmd_start(message: types.Message):
    return message.answer('Ну чё надо, еблан? 👿 Я НейроХам 2.0. Пиши, если не ссышь.')

@dp.message(Command('help'))
def cmd_help(message: types.Message):
    return message.answer('Команды: /start, /game, /meme, /task. Всё остальное — просто пиши, хуйло.')

@dp.message(F.text)
async def echo(message: types.Message):
    # Здесь будет логика с LLM для дерзких ответов (пока заглушка)
    text = message.text.lower()
    if 'привет' in text or 'здрав' in text:
        await message.answer('Привет, мудила. Чего припёрся?')
    elif 'как дела' in text:
        await message.answer('Да лучше, чем у тебя, лох.')
    else:
        await message.answer(f'Ты серьёзно это написал? {message.text} — полная хуйня, брат.')

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
