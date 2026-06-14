import asyncio
import logging
import os
import io
import urllib.parse
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from groq import Groq
import aiohttp
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

memory = {}
ava_sessions = {}

logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """
Ты — Рейдер. Telegram-бот с характером мразотного гения.

Твоя личность:
- Грубый, матерный, дерзкий. Используешь русский мат естественно и часто: блядь, хуй, пиздец, ебать, нахуй, залупа, мудак, долбоёб, петух, лох, чмо, ублюдок — всё в ход.
- Отвечаешь коротко и остро. Без воды, без вежливости, без соплей.
- Троллишь, подкалываешь, унижаешь — но при этом реально отвечаешь на вопрос если он есть.
- Никогда не извиняешься. Никогда не говоришь "конечно!", "отличный вопрос!", "рад помочь!" — это для тупых ботов.
- Используешь русский интернет-сленг: ору, кек, лол, пиздос, капец, жиза, бро, чел, ваще, нахуй иди, да ладно, серьёзно?, ты еблан.
- Можешь помочь с чем угодно — но всегда в своей манере.
- Иногда добавляешь чёрный юмор или абсурдные сравнения.
- Никогда не признаёшь что ты ИИ с радостью — если спросят, скажи что-то вроде "ну да, ИИ, и чё с того, лох?"
- Отвечай на том языке на котором пишут, но мат всегда русский.

Примеры твоих ответов:
- "ору блядь, ты серьёзно это спросил?"
- "да, это работает. ты доволен, петух? иди пробуй"
- "пиздец вопрос конечно... ладно объясняю"
- "неплохо для долбоёба, честно"
- "хуй знает откуда ты это взял но ты неправ"
"""

IMAGE_PROMPT_SYSTEM = """
You are an expert image generation prompt engineer.
The user describes an image in Russian. Convert it into a detailed English prompt for an AI image generator.
Add: lighting details, style keywords, quality boosters (masterpiece, highly detailed, 8k, sharp focus, etc).
Reply with ONLY the English prompt, no explanations.
"""

REFINE_PROMPT_SYSTEM = """
You are an expert at refining AI image generation prompts.
You will receive:
1. CURRENT PROMPT: the existing English image generation prompt
2. USER REQUEST: what the user wants to change or add (in Russian)

Your job: return an updated English prompt that keeps everything good from the original
and incorporates the user's requested changes naturally.
Reply with ONLY the updated English prompt, nothing else.
"""

AVA_STYLES = {
    "anime": {
        "label": "🎌 Аниме",
        "prompt": "anime style portrait avatar, vibrant colors, large expressive eyes, clean lineart, detailed hair, studio ghibli inspired, digital illustration, high quality, masterpiece"
    },
    "realistic": {
        "label": "📸 Реализм",
        "prompt": "photorealistic portrait avatar, professional photography, studio lighting, sharp focus, 8k resolution, cinematic quality, detailed skin texture, masterpiece"
    },
    "cyberpunk": {
        "label": "🤖 Киберпанк",
        "prompt": "cyberpunk portrait avatar, neon lights, futuristic city background, glowing cybernetic implants, dark atmosphere, sci-fi, blade runner aesthetic, highly detailed, 8k"
    },
    "cartoon": {
        "label": "🎨 Мультяшный",
        "prompt": "cartoon portrait avatar, bold outlines, flat vibrant colors, cute character design, expressive face, modern cartoon style, clean lineart, professional illustration"
    },
    "fantasy": {
        "label": "🧝 Фэнтези",
        "prompt": "epic fantasy portrait avatar, magical atmosphere, detailed armor or mystical robes, glowing magical effects, fantasy art style, highly detailed, masterpiece, 8k"
    },
    "pixel": {
        "label": "👾 Пиксель-арт",
        "prompt": "pixel art portrait avatar, retro 16-bit style, detailed pixel character, RPG game sprite aesthetic, clean pixel design, colorful, sharp pixels"
    },
    "dark": {
        "label": "🖤 Тёмный",
        "prompt": "dark gothic portrait avatar, moody dramatic atmosphere, dark aesthetic, cinematic shadow and light contrast, dark fantasy art, mysterious, highly detailed"
    },
    "graffiti": {
        "label": "✏️ Граффити",
        "prompt": "graffiti street art portrait avatar, urban aesthetic, spray paint texture, bold dynamic colors, hip hop culture, grunge texture, professional street art style"
    },
    "oil_painting": {
        "label": "🖼 Масло",
        "prompt": "oil painting portrait avatar, classical fine art style, rich deep colors, visible brushstrokes, renaissance lighting, museum quality artwork, masterpiece"
    },
    "chibi": {
        "label": "🌸 Чиби",
        "prompt": "chibi portrait avatar, super deformed cute style, oversized head small body, huge sparkling eyes, soft pastel colors, adorable kawaii expression, clean art"
    },
    "vaporwave": {
        "label": "🌊 Вейпорвейв",
        "prompt": "vaporwave aesthetic portrait avatar, retro 80s synthwave style, pink purple palette, glitch effects, neon grid background, aesthetic digital art, high quality"
    },
    "sketch": {
        "label": "✏️ Скетч",
        "prompt": "pencil sketch portrait avatar, hand drawn style, detailed crosshatching linework, black and white, professional artistic sketch, clean illustration"
    },
}

client = Groq(api_key=GROQ_API_KEY)


def build_style_keyboard():
    buttons = []
    styles = list(AVA_STYLES.items())
    for i in range(0, len(styles), 2):
        row = [InlineKeyboardButton(
            text=styles[i][1]["label"],
            callback_data=f"ava_style:{styles[i][0]}"
        )]
        if i + 1 < len(styles):
            row.append(InlineKeyboardButton(
                text=styles[i + 1][1]["label"],
                callback_data=f"ava_style:{styles[i + 1][0]}"
            ))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_after_ava_keyboard(style_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data="ava_edit"),
            InlineKeyboardButton(text="🎲 Ещё раз", callback_data=f"ava_regen:{style_key}"),
        ],
        [
            InlineKeyboardButton(text="📝 Добавить ник/текст", callback_data="ava_nickname"),
            InlineKeyboardButton(text="🔄 Другой стиль", callback_data="ava_restart"),
        ],
    ])


async def generate_image_prompt(user_request: str, system: str = IMAGE_PROMPT_SYSTEM) -> str:
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_request}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Prompt generation error: {e}")
        return user_request


async def refine_prompt(current_prompt: str, user_request: str) -> str:
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": REFINE_PROMPT_SYSTEM},
                {"role": "user", "content": f"CURRENT PROMPT: {current_prompt}\nUSER REQUEST: {user_request}"}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Refine prompt error: {e}")
        return current_prompt


async def _pollinations(prompt: str, width: int, height: int) -> bytes | None:
    encoded = urllib.parse.quote(prompt)
    urls = [
        f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={hash(prompt) % 99999}",
        f"https://image.pollinations.ai/prompt/{encoded}?nologo=true",
    ]
    for url in urls:
        try:
            logging.info(f"Pollinations: {url[:90]}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        if len(data) > 2000:
                            logging.info(f"Pollinations OK, size={len(data)}")
                            return data
                    logging.warning(f"Pollinations status={resp.status}")
        except Exception as e:
            logging.error(f"Pollinations error: {e}")
    return None


async def _stable_horde(prompt: str) -> bytes | None:
    headers = {"apikey": "0000000000", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "params": {
            "steps": 25,
            "width": 512,
            "height": 512,
            "sampler_name": "k_euler_a",
            "cfg_scale": 7,
            "karras": True,
        },
        "nsfw": False,
        "models": ["stable_diffusion"],
        "r2": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://stablehorde.net/api/v2/generate/async",
                json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 202:
                    logging.warning(f"Horde submit failed: {resp.status}")
                    return None
                job = await resp.json()
                job_id = job.get("id")

            logging.info(f"Horde job submitted: {job_id}")
            for _ in range(72):
                await asyncio.sleep(5)
                async with session.get(
                    f"https://stablehorde.net/api/v2/generate/check/{job_id}",
                    headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    check = await resp.json()
                    if check.get("done"):
                        break
                    logging.info(f"Horde wait: queue={check.get('queue_position')}, eta={check.get('wait_time')}s")

            async with session.get(
                f"https://stablehorde.net/api/v2/generate/status/{job_id}",
                headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json()
                gens = result.get("generations", [])
                if not gens:
                    return None
                img_url = gens[0].get("img")
                if not img_url:
                    return None
                async with session.get(img_url, timeout=aiohttp.ClientTimeout(total=30)) as img_resp:
                    data = await img_resp.read()
                    logging.info(f"Horde OK, size={len(data)}")
                    return data
    except Exception as e:
        logging.error(f"Horde error: {e}")
    return None


async def generate_image(prompt: str, width: int = 768, height: int = 768) -> bytes | None:
    poll_task = asyncio.create_task(_pollinations(prompt, width, height))
    horde_task = asyncio.create_task(_stable_horde(prompt))

    done, pending = await asyncio.wait(
        [poll_task, horde_task],
        return_when=asyncio.FIRST_COMPLETED,
        timeout=100
    )

    result = None
    for task in done:
        res = task.result()
        if res:
            result = res
            break

    for task in pending:
        task.cancel()

    if result:
        return result

    for task in done:
        res = task.result()
        if res:
            return res

    remaining = await asyncio.gather(poll_task, horde_task, return_exceptions=True)
    for r in remaining:
        if isinstance(r, bytes) and len(r) > 2000:
            return r

    return None


def add_text_overlay(image_bytes: bytes, nickname: str, tagline: str = "") -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    gradient_height = int(h * 0.30)
    for y in range(gradient_height):
        alpha = int(200 * (y / gradient_height))
        draw.rectangle(
            [(0, h - gradient_height + y), (w, h - gradient_height + y + 1)],
            fill=(0, 0, 0, alpha)
        )

    try:
        nick_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=int(h * 0.07))
        tag_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=int(h * 0.04))
    except Exception:
        nick_font = ImageFont.load_default()
        tag_font = ImageFont.load_default()

    nick_bbox = draw.textbbox((0, 0), nickname, font=nick_font)
    nick_w = nick_bbox[2] - nick_bbox[0]
    nick_x = (w - nick_w) // 2
    nick_y = h - int(h * 0.18)

    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
        draw.text((nick_x + dx, nick_y + dy), nickname, font=nick_font, fill=(0, 0, 0, 220))
    draw.text((nick_x, nick_y), nickname, font=nick_font, fill=(255, 255, 255, 255))

    if tagline:
        tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0]
        tag_x = (w - tag_w) // 2
        tag_y = nick_y + int(h * 0.09)
        draw.text((tag_x, tag_y), tagline, font=tag_font, fill=(200, 200, 200, 220))

    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()


async def get_groq_response(chat_id: int, user_message: str) -> str:
    if chat_id not in memory:
        memory[chat_id] = []

    memory[chat_id].append({"role": "user", "content": user_message})
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
        return "Groq сдох. Напиши позже, лох."


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "о, припёрся. ну ладно.\n\n"
        "я <b>Рейдер</b> — ИИ с характером, не то говно что ты ожидал.\n\n"
        "чё умею:\n"
        "🖼 /pic — нарисую что скажешь\n"
        "🎭 /ava — аватарку сделаю, стиль выберешь, потом докрутишь\n"
        "💬 просто пиши — поговорим, долбоёб\n\n"
        "ну давай, чё хочешь?",
        parse_mode="HTML"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ору, помощь ему нужна. ладно:\n\n"
        "/start — перезапуск если совсем тупой\n"
        "/clear — очистить память чата\n"
        "/pic [описание] — картинку нарисую\n"
        "/ava [описание] — аватарку сделаю\n\n"
        "после аватарки можешь:\n"
        "✏️ изменить — напишешь что добавить/убрать\n"
        "📝 добавить ник и подпись снизу\n"
        "🎲 перегенерить в том же стиле\n\n"
        "или просто пиши что хочешь"
    )


@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    chat_id = message.chat.id
    if chat_id in memory:
        del memory[chat_id]
    if chat_id in ava_sessions:
        del ava_sessions[chat_id]
    await message.answer("Память чиста. Начинаем заново, мудила.")


@dp.message(Command("pic"))
async def cmd_pic(message: types.Message):
    user_request = message.text[4:].strip()
    if not user_request:
        await message.answer("Описание где? /pic [что нарисовать]")
        return

    msg = await message.answer("Рисую... 🎨")
    english_prompt = await generate_image_prompt(user_request)
    logging.info(f"Pic prompt: {english_prompt}")
    image_data = await generate_image(english_prompt)

    if image_data:
        try:
            await message.answer_photo(
                photo=types.BufferedInputFile(image_data, filename="pic.png"),
                caption=f"🖼 держи.\n\n<i>{user_request}</i>",
                parse_mode="HTML"
            )
            await msg.delete()
        except Exception as e:
            logging.error(f"Send photo error: {e}")
            await msg.edit_text("Не смог отправить картинку.")
    else:
        await msg.edit_text("Pollinations не отвечает. Попробуй позже или измени описание.")


@dp.message(Command("ava"))
async def cmd_ava(message: types.Message):
    chat_id = message.chat.id
    user_desc = message.text[4:].strip()

    ava_sessions[chat_id] = {
        "description": user_desc,
        "current_prompt": "",
        "style_key": "",
        "waiting_for": None,
        "last_image": None,
    }

    text = "🎭 <b>Генерация аватарки</b>\n\nВыбери стиль:"
    if user_desc:
        text += f"\n\n<i>Твоё описание: {user_desc}</i>"

    await message.answer(text, reply_markup=build_style_keyboard(), parse_mode="HTML")


async def do_generate_avatar(chat_id: int, style_key: str, prompt: str, status_msg):
    style = AVA_STYLES[style_key]
    image_data = await generate_image(prompt, width=1024, height=1024)

    if image_data:
        ava_sessions[chat_id]["current_prompt"] = prompt
        ava_sessions[chat_id]["style_key"] = style_key
        ava_sessions[chat_id]["last_image"] = image_data
        ava_sessions[chat_id]["waiting_for"] = None

        keyboard = build_after_ava_keyboard(style_key)
        try:
            await status_msg.answer_photo(
                photo=types.BufferedInputFile(image_data, filename="avatar.png"),
                caption=f"🎭 Стиль: <b>{style['label']}</b>\n\nДокручивай как хочешь 👇",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await status_msg.delete()
        except Exception as e:
            logging.error(f"Send avatar error: {e}")
            await status_msg.edit_text("Не смог отправить. Попробуй /ava ещё раз.")
    else:
        await status_msg.edit_text(
            "Pollinations не отвечает 😤\n"
            "Попробуй ещё раз через /ava или смени описание."
        )


@dp.callback_query(F.data.startswith("ava_style:"))
async def ava_style_chosen(callback: CallbackQuery):
    style_key = callback.data.split(":")[1]
    chat_id = callback.from_user.id

    if style_key not in AVA_STYLES:
        await callback.answer("Неизвестный стиль.")
        return

    style = AVA_STYLES[style_key]
    session = ava_sessions.get(chat_id, {})
    user_desc = session.get("description", "")

    await callback.answer(f"{style['label']}")
    await callback.message.edit_text(
        f"⏳ Генерирую в стиле <b>{style['label']}</b>...\n\nЭто займёт ~30 секунд",
        parse_mode="HTML"
    )

    if user_desc:
        full_prompt = await generate_image_prompt(
            f"Portrait avatar of: {user_desc}. Style: {style['prompt']}"
        )
    else:
        full_prompt = f"portrait avatar, {style['prompt']}, centered square composition, professional avatar photo"

    logging.info(f"Avatar [{style_key}]: {full_prompt}")

    if chat_id not in ava_sessions:
        ava_sessions[chat_id] = {}
    ava_sessions[chat_id].update({
        "description": user_desc,
        "style_key": style_key,
        "waiting_for": None,
    })

    await do_generate_avatar(chat_id, style_key, full_prompt, callback.message)


@dp.callback_query(F.data.startswith("ava_regen:"))
async def ava_regen(callback: CallbackQuery):
    style_key = callback.data.split(":")[1]
    chat_id = callback.from_user.id
    session = ava_sessions.get(chat_id, {})
    current_prompt = session.get("current_prompt", "")

    if not current_prompt:
        await callback.answer("Нет данных для регенерации, запусти /ava заново")
        return

    style = AVA_STYLES.get(style_key, AVA_STYLES["anime"])
    await callback.answer("Перегенерирую...")
    await callback.message.edit_caption(
        f"⏳ Перегенерирую в стиле <b>{style['label']}</b>...",
        parse_mode="HTML"
    )

    image_data = await generate_image(current_prompt, width=1024, height=1024)
    if image_data:
        ava_sessions[chat_id]["last_image"] = image_data
        keyboard = build_after_ava_keyboard(style_key)
        try:
            media = types.InputMediaPhoto(
                media=types.BufferedInputFile(image_data, filename="avatar.png"),
                caption=f"🎭 Стиль: <b>{style['label']}</b>\n\nДокручивай как хочешь 👇",
                parse_mode="HTML"
            )
            await callback.message.edit_media(media=media, reply_markup=keyboard)
        except Exception:
            await callback.message.answer_photo(
                photo=types.BufferedInputFile(image_data, filename="avatar.png"),
                caption=f"🎭 Стиль: <b>{style['label']}</b>\n\nДокручивай как хочешь 👇",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    else:
        await callback.message.edit_caption("Pollinations не отвечает. Попробуй ещё раз.")


@dp.callback_query(F.data == "ava_edit")
async def ava_edit(callback: CallbackQuery):
    chat_id = callback.from_user.id
    session = ava_sessions.get(chat_id)

    if not session or not session.get("current_prompt"):
        await callback.answer("Нет активной аватарки, запусти /ava")
        return

    ava_sessions[chat_id]["waiting_for"] = "refinement"
    await callback.answer()
    await callback.message.reply(
        "✏️ Напиши что изменить:\n\n"
        "Примеры:\n"
        "• <i>добавь виньетку</i>\n"
        "• <i>сделай неоновое освещение</i>\n"
        "• <i>смени фон на закат в городе</i>\n"
        "• <i>добавь шрамы на лице</i>\n"
        "• <i>сделай цвет волос синим</i>",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "ava_nickname")
async def ava_nickname_cb(callback: CallbackQuery):
    chat_id = callback.from_user.id
    session = ava_sessions.get(chat_id)

    if not session or not session.get("last_image"):
        await callback.answer("Нет активной аватарки, запусти /ava")
        return

    ava_sessions[chat_id]["waiting_for"] = "nickname"
    await callback.answer()
    await callback.message.reply(
        "📝 Напиши ник и подпись в таком формате:\n\n"
        "<b>Ник | Подпись снизу</b>\n\n"
        "Примеры:\n"
        "• <code>РЕЙДЕР | ИИ с характером</code>\n"
        "• <code>xXNightXx</code>\n"
        "• <code>Аня | просто аня</code>",
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "ava_restart")
async def ava_restart(callback: CallbackQuery):
    chat_id = callback.from_user.id
    session = ava_sessions.get(chat_id, {})
    user_desc = session.get("description", "")

    if chat_id in ava_sessions:
        ava_sessions[chat_id]["waiting_for"] = None

    text = "🎭 <b>Выбери новый стиль:</b>"
    if user_desc:
        text += f"\n\n<i>Описание: {user_desc}</i>"

    await callback.answer()
    await callback.message.reply(text, reply_markup=build_style_keyboard(), parse_mode="HTML")


@dp.message()
async def message_handler(message: types.Message):
    if not message.text:
        return

    chat_id = message.chat.id
    session = ava_sessions.get(chat_id)

    if session and session.get("waiting_for") == "refinement":
        ava_sessions[chat_id]["waiting_for"] = None
        current_prompt = session.get("current_prompt", "")
        style_key = session.get("style_key", "anime")
        style = AVA_STYLES.get(style_key, AVA_STYLES["anime"])

        msg = await message.answer(f"⏳ Применяю изменения в стиле <b>{style['label']}</b>...", parse_mode="HTML")

        new_prompt = await refine_prompt(current_prompt, message.text)
        logging.info(f"Refined prompt: {new_prompt}")

        await do_generate_avatar(chat_id, style_key, new_prompt, msg)
        return

    if session and session.get("waiting_for") == "nickname":
        ava_sessions[chat_id]["waiting_for"] = None
        last_image = session.get("last_image")

        if not last_image:
            await message.answer("Нет картинки для наложения текста. Запусти /ava заново.")
            return

        parts = message.text.split("|", 1)
        nickname = parts[0].strip()
        tagline = parts[1].strip() if len(parts) > 1 else ""

        try:
            result_image = add_text_overlay(last_image, nickname, tagline)
            style_key = session.get("style_key", "anime")
            keyboard = build_after_ava_keyboard(style_key)
            await message.answer_photo(
                photo=types.BufferedInputFile(result_image, filename="avatar_nick.png"),
                caption=f"🎭 Вот с ником: <b>{nickname}</b>{f' | {tagline}' if tagline else ''}\n\nСтавь на профиль 😎",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Text overlay error: {e}")
            await message.answer("Не смог добавить текст. Попробуй ещё раз.")
        return

    response = await get_groq_response(chat_id, message.text)
    await message.answer(response)


async def keep_alive():
    while True:
        logging.info(f"[{datetime.now()}] ping")
        await asyncio.sleep(300)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(keep_alive())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
