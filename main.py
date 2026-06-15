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
You are an expert image generation prompt engineer specializing in cinematic anime profile avatars.
The user describes an image in Russian. Convert it into a detailed English prompt for Stable Diffusion.

CRITICAL RULES for avatar prompts:
- Always include: masterpiece, best quality, ultra-detailed, sharp focus, 8k
- Always make it a SQUARE PORTRAIT (centered composition, face/upper body)
- Add dramatic effects: glowing aura, particle effects, energy lightning, volumetric light rays, atmospheric haze
- Dark cinematic background with colored glow (NOT plain/flat/simple backgrounds)
- Character should look intense/cool, looking at viewer
- Add depth with: depth of field, bokeh background, foreground elements
- Style: professional digital art, concept art quality

Reply with ONLY the English prompt, no explanations.
"""

REFINE_PROMPT_SYSTEM = """
You are an expert at refining AI image generation prompts for cinematic anime avatars.
You will receive:
1. CURRENT PROMPT: the existing English image generation prompt
2. USER REQUEST: what the user wants to change or add (in Russian)

Your job: return an updated English prompt that keeps everything good from the original
and incorporates the user's requested changes naturally.
Always keep: masterpiece, best quality, dramatic effects, cinematic atmosphere.
Reply with ONLY the updated English prompt, nothing else.
"""

NEGATIVE_PROMPT_BASE = "lowres, bad anatomy, bad hands, text, watermark, signature, username, error, blurry, jpeg artifacts, cropped, worst quality, low quality, normal quality, ugly, deformed, mutation, extra limbs, missing limbs, flat background, plain background, simple background, solid background, white background, gradient background, boring background, washed out colors, overexposed, underexposed, bad composition, amateur"

NEGATIVE_PROMPT_ANIME = f"{NEGATIVE_PROMPT_BASE}, 3d render, photorealistic, cgi, realistic skin, poorly drawn face, bad face, fused body, extra fingers, missing fingers"

NEGATIVE_PROMPT_REAL = f"{NEGATIVE_PROMPT_BASE}, anime, cartoon, illustration, painting, drawing, 3d, cgi, deformed face"

AVA_STYLES = {
    "anime": {
        "label": "🎌 Аниме",
        "models": ["Dreamshaper", "Nova Anime XL", "Abyss OrangeMix"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic anime portrait avatar:1.3), dramatic character, intense expression looking at viewer, dynamic pose, highly detailed anime face, detailed hair with highlights, glowing aura around body, particle effects floating, volumetric light rays, dark atmospheric background with colored bokeh lights, depth of field, sharp focus on face, professional digital art, concept art, 8k resolution, vibrant colors"
    },
    "realistic": {
        "label": "📸 Реализм",
        "models": ["Dreamshaper", "Deliberate"],
        "negative": NEGATIVE_PROMPT_REAL,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic portrait avatar:1.3), professional photography, dramatic studio lighting, rim light, octane render quality, photorealistic face, detailed skin texture, intense expression looking at viewer, dark moody background with bokeh, volumetric fog, cinematic color grading, sharp focus, 8k resolution, award winning photography"
    },
    "cyberpunk": {
        "label": "🤖 Киберпанк",
        "models": ["Dreamshaper", "Abyss OrangeMix"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic cyberpunk anime portrait avatar:1.3), neon blue and purple glowing effects, cybernetic implants glowing, futuristic dark city background with rain reflections, neon light particles, electric sparks, circuit pattern aura, dramatic neon rim lighting, intense expression looking at viewer, dark atmospheric fog, holographic elements, 8k, sharp focus"
    },
    "cartoon": {
        "label": "🎨 Мультяшный",
        "models": ["Dreamshaper", "Nova Anime XL"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic cartoon portrait avatar:1.3), bold clean lineart, vibrant saturated colors, dramatic lighting with colored shadows, expressive face looking at viewer, dynamic stylized background with geometric shapes and light rays, professional cartoon illustration, thick outlines, cel-shaded, sharp and clean, modern animation style, 8k"
    },
    "fantasy": {
        "label": "🧝 Фэнтези",
        "models": ["Dreamshaper", "Nova Anime XL"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (epic fantasy anime portrait avatar:1.3), dramatic magical aura with glowing runes, fantasy armor or mystical robes with intricate details, magical particles and sparkles floating, intense expression looking at viewer, dark mystical background with glowing magical circles, volumetric light from magic, ethereal atmosphere, deep colors, 8k, sharp focus"
    },
    "pixel": {
        "label": "👾 Пиксель-арт",
        "models": ["Deliberate", "Dreamshaper"],
        "negative": f"{NEGATIVE_PROMPT_BASE}, blurry, anti-aliased, smooth",
        "prompt": "masterpiece, best quality, (detailed pixel art portrait avatar:1.3), retro 16-bit RPG game style, crisp sharp pixels, detailed pixel character face, dynamic pixel art background with pixel effects and particles, vibrant pixel colors, clean pixel lineart, RPG character portrait, pixel art shading, professional pixel art, 8k equivalent detail"
    },
    "dark": {
        "label": "🖤 Тёмный",
        "models": ["Dreamshaper", "Abyss OrangeMix"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (dark cinematic anime portrait avatar:1.3), dramatic dark atmosphere, deep shadows, glowing red or purple energy aura, shadow particles disintegrating, intense cold expression looking at viewer, dark background with subtle dark fog and distant glow, cinematic shadow lighting from below, contrast between darkness and glow, menacing atmosphere, 8k, sharp focus"
    },
    "graffiti": {
        "label": "🎭 Граффити",
        "models": ["Deliberate", "Dreamshaper"],
        "negative": NEGATIVE_PROMPT_BASE,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic graffiti art portrait avatar:1.3), bold spray paint texture, vibrant saturated colors, dynamic urban background with graffiti wall and street elements, paint splatter effects, dramatic hip hop aesthetic, expressive character looking at viewer, bold black outlines, professional street art style, urban particles, dripping paint effects, 8k"
    },
    "oil_painting": {
        "label": "🖼 Масло",
        "models": ["Dreamshaper", "Deliberate"],
        "negative": NEGATIVE_PROMPT_REAL,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic oil painting portrait avatar:1.3), rich deep brushstrokes visible, classical fine art style, dramatic chiaroscuro lighting, dark moody atmospheric background, renaissance composition, rich saturated colors, warm golden rim light, museum quality artwork, painted texture, intense character expression looking at viewer, 8k"
    },
    "chibi": {
        "label": "🌸 Чиби",
        "models": ["Dreamshaper", "Nova Anime XL"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (cute chibi anime portrait avatar:1.3), super deformed style, oversized head small body, huge sparkly glowing eyes, soft glowing pastel background with stars and sparkles, adorable kawaii expression, pastel color palette, soft lighting, clean smooth lineart, magical particle effects, floating hearts and stars, 8k, sharp"
    },
    "vaporwave": {
        "label": "🌊 Вейпорвейв",
        "models": ["Dreamshaper", "Abyss OrangeMix"],
        "negative": NEGATIVE_PROMPT_ANIME,
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic vaporwave anime portrait avatar:1.3), retrowave aesthetic, neon pink purple and cyan palette, glitch effects on edges, synthwave grid background with sunset, neon glow outline around character, retro 80s japanese aesthetic, VHS scanlines overlay, neon particle effects, intense look at viewer, chromatic aberration, dramatic neon lighting, 8k"
    },
    "sketch": {
        "label": "✏️ Скетч",
        "models": ["Deliberate", "Dreamshaper"],
        "negative": f"{NEGATIVE_PROMPT_BASE}, color, colorful, painted",
        "prompt": "masterpiece, best quality, ultra-detailed, (cinematic pencil sketch portrait avatar:1.3), dramatic black and white, detailed crosshatching and linework, professional concept art sketch, intense expression looking at viewer, dynamic sketch lines suggesting motion, ink wash shading, strong contrast between black ink and white paper, loose energetic sketch strokes, artist's sketchbook quality, 8k equivalent"
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


async def download_telegram_photo(file_id: str) -> str | None:
    """Download a Telegram photo and return it as base64 string (resized to 768x768)."""
    import base64 as b64mod
    try:
        file = await bot.get_file(file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img = img.resize((768, 768), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return b64mod.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        logging.error(f"download_telegram_photo error: {e}")
        return None


async def generate_image(
    prompt: str,
    width: int = 512,
    height: int = 512,
    negative_prompt: str = "",
    models: list = None,
    source_image_b64: str = None,
    denoising_strength: float = 0.75
) -> bytes | None:
    import base64 as b64mod
    horde_key = os.environ.get("HORDE_API_KEY", "0000000000")
    api_headers = {"apikey": horde_key, "Content-Type": "application/json", "Client-Agent": "RaiderBot:2.0:tg"}
    if models is None:
        models = ["Dreamshaper"]
    full_prompt = prompt
    if negative_prompt:
        full_prompt = f"{prompt} ### {negative_prompt}"
    payload = {
        "prompt": full_prompt,
        "params": {
            "steps": 28,
            "width": width,
            "height": height,
            "sampler_name": "k_dpmpp_2m",
            "cfg_scale": 8,
            "karras": True,
            "hires_fix": False,
            "clip_skip": 2,
            "denoising_strength": denoising_strength if source_image_b64 else 1.0,
        },
        "nsfw": False,
        "models": models,
        "r2": False,
        "shared": True,
        "slow_workers": True,
    }
    if source_image_b64:
        payload["source_image"] = source_image_b64
        payload["source_processing"] = "img2img"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://stablehorde.net/api/v2/generate/async",
                json=payload, headers=api_headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 202:
                    logging.warning(f"Horde submit failed: {resp.status} — {await resp.text()}")
                    return None
                job = await resp.json()
                job_id = job.get("id")

            if not job_id:
                logging.error("Horde: no job_id in response")
                return None

            logging.info(f"Horde job submitted: {job_id}")

            for attempt in range(80):
                await asyncio.sleep(5)
                try:
                    async with session.get(
                        f"https://stablehorde.net/api/v2/generate/check/{job_id}",
                        headers=api_headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        check = await resp.json()
                        is_done = check.get("done", False)
                        queue = check.get("queue_position", "?")
                        eta = check.get("wait_time", "?")
                        logging.info(f"Horde [{attempt}]: done={is_done} queue={queue} eta={eta}s")
                        if is_done:
                            break
                except Exception as e:
                    logging.warning(f"Horde check error: {e}")
                    continue

            async with session.get(
                f"https://stablehorde.net/api/v2/generate/status/{job_id}",
                headers=api_headers,
                timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                result = await resp.json()

            gens = result.get("generations", [])
            if not gens:
                logging.warning(f"Horde: no generations. Full response: {result}")
                return None

            img_data = gens[0].get("img", "")
            if not img_data:
                logging.warning("Horde: img field is empty")
                return None

            if img_data.startswith("http"):
                async with session.get(img_data, timeout=aiohttp.ClientTimeout(total=30)) as img_resp:
                    data = await img_resp.read()
            else:
                data = b64mod.b64decode(img_data)

            logging.info(f"Horde OK, size={len(data)}")
            return data

    except Exception as e:
        logging.error(f"Horde error: {e}")
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
    image_data = await generate_image(
        english_prompt,
        negative_prompt=NEGATIVE_PROMPT_BASE,
        models=["Dreamshaper", "Deliberate"]
    )

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
        await msg.edit_text("Генерация не удалась. Попробуй позже или измени описание.")


@dp.message(Command("ava"))
async def cmd_ava(message: types.Message):
    chat_id = message.chat.id
    user_desc = message.text[4:].strip()

    prev = ava_sessions.get(chat_id, {})
    ava_sessions[chat_id] = {
        "description": user_desc,
        "current_prompt": "",
        "style_key": "",
        "waiting_for": None,
        "last_image": None,
        "ref_image_b64": prev.get("ref_image_b64"),
        "ref_mode": prev.get("ref_mode"),
        "ref_denoising": prev.get("ref_denoising", 0.75),
    }

    text = "🎭 <b>Генерация аватарки</b>\n\nВыбери стиль:"
    if user_desc:
        text += f"\n\n<i>Твоё описание: {user_desc}</i>"
    if prev.get("ref_mode"):
        mode_labels = {"background": "🖼 фон", "style": "🎨 стиль", "atmosphere": "🌈 атмосфера"}
        text += f"\n\n<i>📎 Референс активен: {mode_labels.get(prev.get('ref_mode'), prev.get('ref_mode'))}</i>"

    await message.answer(text, reply_markup=build_style_keyboard(), parse_mode="HTML")


async def do_generate_avatar(chat_id: int, style_key: str, prompt: str, status_msg):
    style = AVA_STYLES[style_key]
    session = ava_sessions.get(chat_id, {})
    ref_b64 = session.get("ref_image_b64")
    ref_denoising = session.get("ref_denoising", 0.75)
    image_data = await generate_image(
        prompt,
        width=768, height=768,
        negative_prompt=style.get("negative", NEGATIVE_PROMPT_BASE),
        models=style.get("models", ["Dreamshaper"]),
        source_image_b64=ref_b64,
        denoising_strength=ref_denoising
    )

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
            "Генерация не удалась 😤\n"
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
        f"⏳ Генерирую в стиле <b>{style['label']}</b>...\n\nМожет занять 1-3 минуты, не закрывай чат",
        parse_mode="HTML"
    )

    if user_desc:
        full_prompt = await generate_image_prompt(
            f"Cinematic avatar portrait. Character description: {user_desc}. Base style reference: {style['prompt']}"
        )
    else:
        full_prompt = style["prompt"]

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

    image_data = await generate_image(
        current_prompt,
        width=768, height=768,
        negative_prompt=style.get("negative", NEGATIVE_PROMPT_BASE),
        models=style.get("models", ["Dreamshaper"])
    )
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
        await callback.message.edit_caption("Генерация не удалась. Попробуй ещё раз.")


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


def build_ref_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🖼 Использовать как фон", callback_data="ref_mode:background"),
            InlineKeyboardButton(text="🎨 Скопировать стиль", callback_data="ref_mode:style"),
        ],
        [
            InlineKeyboardButton(text="🌈 Взять атмосферу/цвета", callback_data="ref_mode:atmosphere"),
            InlineKeyboardButton(text="❌ Не использовать", callback_data="ref_mode:cancel"),
        ],
    ])


@dp.message(F.photo)
async def photo_handler(message: types.Message):
    chat_id = message.chat.id
    caption = message.caption or ""

    await message.answer(
        "📎 <b>Фото получено!</b>\n\n"
        "Что с ним делаем при генерации авы?\n\n"
        "• <b>Фон</b> — твоё фото станет основой, бот добавит персонажа сверху\n"
        "• <b>Стиль</b> — бот скопирует арт-стиль/рисовку с этого фото\n"
        "• <b>Атмосфера</b> — возьмёт цвета и настроение\n",
        reply_markup=build_ref_keyboard(),
        parse_mode="HTML"
    )

    file_id = message.photo[-1].file_id
    if chat_id not in ava_sessions:
        ava_sessions[chat_id] = {}
    ava_sessions[chat_id]["_pending_file_id"] = file_id
    if caption:
        ava_sessions[chat_id]["description"] = caption


@dp.callback_query(F.data.startswith("ref_mode:"))
async def ref_mode_chosen(callback: CallbackQuery):
    chat_id = callback.from_user.id
    mode = callback.data.split(":")[1]

    if mode == "cancel":
        if chat_id in ava_sessions:
            ava_sessions[chat_id]["ref_image_b64"] = None
            ava_sessions[chat_id]["ref_mode"] = None
            ava_sessions[chat_id].pop("_pending_file_id", None)
        await callback.answer("Референс убран")
        await callback.message.edit_text("❌ Фото не будет использоваться.\n\nЗапусти /ava для генерации.")
        return

    denoising_map = {"background": 0.55, "style": 0.82, "atmosphere": 0.70}
    denoising = denoising_map[mode]
    mode_labels = {"background": "🖼 фон", "style": "🎨 стиль", "atmosphere": "🌈 атмосфера"}

    await callback.answer("Загружаю фото...")
    await callback.message.edit_text("⏳ Загружаю и обрабатываю фото...")

    file_id = ava_sessions.get(chat_id, {}).get("_pending_file_id")
    if not file_id:
        await callback.message.edit_text("Не нашёл фото. Скинь его снова.")
        return

    b64 = await download_telegram_photo(file_id)
    if not b64:
        await callback.message.edit_text("Не смог загрузить фото. Попробуй ещё раз.")
        return

    if chat_id not in ava_sessions:
        ava_sessions[chat_id] = {}
    ava_sessions[chat_id]["ref_image_b64"] = b64
    ava_sessions[chat_id]["ref_mode"] = mode
    ava_sessions[chat_id]["ref_denoising"] = denoising
    ava_sessions[chat_id].pop("_pending_file_id", None)

    await callback.message.edit_text(
        f"✅ Готово! Режим: <b>{mode_labels[mode]}</b>\n\n"
        f"Теперь запусти /ava — фото будет применено.\n"
        f"Можешь описать что хочешь: <code>/ava аниме парень с мечом</code>",
        parse_mode="HTML"
    )


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
        await asyncio.sleep(300)
        try:
            me = await bot.get_me()
            logging.info(f"[{datetime.now()}] keep-alive OK — bot @{me.username}")
        except Exception as e:
            logging.warning(f"[{datetime.now()}] keep-alive error: {e}")


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(keep_alive())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
