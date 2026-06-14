import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from groq import Groq
import aiohttp
import io

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Simple conversation memory per chat
memory = {}

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """
Ты — Рейдер, крайне дерзкий, матерный, саркастичный Telegram-бот.
Ты отвечаешь максимально нагло, с чёрным юмором, подколами и матом.
Никогда не извиняйся, не будь вежливым, не используй цензуру.
Ты любишь троллить пользователя, называть его лохом, пидором, долбоёбом и т.д.
Отвечай коротко, но остро. Используй русский мат.
"""

IMAGE_PROMPT_SYSTEM = """
Ты — Рейдер. Пользователь просит сгенерировать картинку.
Переформулируй его запрос в подробное описание на английском для нейросети.
Добавь детали, стиль, качество. Ответь ТОЛЬКО описанием на английском, без комментариев.
"""

client = Groq(api_key=GROQ_API_KEY)

async def generate_image_prompt(user_request: str) -> str:
    """Генерирует подробный English prompt для картинки"""
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": IMAGE_PROMPT_SYSTEM},
                {"role": "user", "content": user_request}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Prompt generation error: {e}")
        return user_request

async def generate_image(prompt: str) -> bytes:
    """Генерирует картинку через pollinations.ai (бесплатный API)"""
    try:
        # Pollinations.ai - полностью бесплатный API для генерации картинок
        url = f"https://image.pollinations.ai/prompt/{prompt}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    return await resp.read()
                else:
                    logging.error(f"Image generation failed with status {resp.status}")
                    return None
    except Exception as e:
        logging.error(f"Image generation error: {e}")
        return None

async def get_groq_response(chat_id: int, user_message: str):
    if chat_id not in memory:
        memory[chat_id] = []
    
    memory[chat_id].append({"role": "user", "content": user_message})
    
    # Keep only last 10 messages
    if len(memory[chat_id]) > 20:
        memory[chat_id] = memory[chat_id][-20:]
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *memory[chat_id]
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.85,
            max_tokens=700,
        )
        response = chat_completion.choices[0].message.content
        memory[chat_id].append({"role": "assistant", "content": response})
        return response
    except Exception as e:
        logging.error(f"Groq error: {e}")
        return "Ебать, даже Groq меня предал. Пиши позже, лох."

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Ну чё, лох, пришёл? Я Рейдер — настоящий ИИ, а не тот говнокод, что был раньше.\n\nПиши что угодно, я буду тебя разъёбывать.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Команды:\n"
        "/start — перезапуск\n"
        "/help — это\n"
        "/clear — очистить память\n"
        "/pic [описание] — сгенерить картинку\n\n"
        "Просто пиши, я буду тебя троллить как надо."
    )

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    chat_id = message.chat.id
    if chat_id in memory:
        del memory[chat_id]
    await message.answer("Память очищена, давай заново, мудила.")

@dp.message(Command("pic"))
async def cmd_pic(message: types.Message):
    """Генерирует картинку по описанию"""
    if not message.text.startswith("/pic"):
        await message.answer("Укажи, что нарисовать, долбоёб.")
        return
    
    user_request = message.text[4:].strip()
    if not user_request:
        await message.answer("Укажи, что рисовать, лох! /pic [описание]")
        return
    
    await message.answer("Генерирую картинку, подожди... 🎨")
    
    # Генерируем подробный English prompt
    english_prompt = await generate_image_prompt(user_request)
    logging.info(f"Generated prompt: {english_prompt}")
    
    # Генерируем картинку
    image_data = await generate_image(english_prompt)
    
    if image_data:
        try:
            await message.answer_photo(
                photo=types.BufferedInputFile(image_data, filename="generated.png"),
                caption=f"Вот, держи, нечего благодарить 😎\n\n_Запрос: {user_request}_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Error sending photo: {e}")
            await message.answer(f"Ебать, картинка слишком большая или что-то пошло не так: {str(e)[:100]}")
    else:
        await message.answer("Сервер картинок глючит, попробуй позже, лох.")

@dp.message()
async def ham_handler(message: types.Message):
    response = await get_groq_response(message.chat.id, message.text)
    await message.answer(response)

# Keep-alive
async def keep_alive():
    while True:
        logging.info(f"[{datetime.now()}] Keep-alive ping")
        await asyncio.sleep(300)  # every 5 minutes

async def main():
    asyncio.create_task(keep_alive())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
