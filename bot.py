import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aiohttp

load_dotenv()


BOT_TOKEN = os.getenv(9003363890:AAFr-Ies_xlUCKYDpUiDUa7dMmVuUk7vRcs)
TMDB_API_KEY = os.getenv(44f880c4a53df795258b8d3cfbb4049d)
KODIK_TOKEN = "447d179e875efe44217f20d1ee2146be"  # Твой рабочий токен
MY_ID = int(os.getenv(662892372))

TMDB_BASE = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"
PLAYER_URL = "https://github.com/bluumod/kinovibe-player/blob/main/index.html"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KinoBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher()
        self.router = Router()
        self.session = None
        self._register_handlers()

    def _register_handlers(self):
        self.router.message.register(self.cmd_start, CommandStart())
        self.router.message.register(self.handle_search, F.text & ~F.text.startswith("/"))
        self.router.callback_query.register(self.cb_select_movie, F.data.startswith("select:"))
        self.router.callback_query.register(self.cb_play, F.data.startswith("play:"))
        self.router.callback_query.register(self.cb_back, F.data == "back")
        self.dp.include_router(self.router)

    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def cmd_start(self, message: Message):
        if message.from_user.id != MY_ID:
            return
        text = "🎬 <b>Kino Vibe</b>\n\nПросто напиши название фильма или сериала (например: <i>Мстители</i> или <i>Во все тяжкие</i>), и я найду его с плеером!"
        await message.answer(text)

    async def handle_search(self, message: Message):
        if message.from_user.id != MY_ID:
            return
        
        query = message.text.strip()
        if len(query) < 2:
            return

        await message.answer(f"🔍 Ищу «{query}»... Подожди пару секунд.")
        session = await self._get_session()
        
        params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
        results = []
        
        async with session.get(f"{TMDB_BASE}/search/multi", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                for item in data.get("results", [])[:8]:
                    if item.get("media_type") in ["movie", "tv"]:
                        title = item.get("title") or item.get("name")
                        year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
                        results.append({
                            "id": item["id"],
                            "type": item["media_type"],
                            "title": title,
                            "year": year
                        })

        if not results:
            await message.answer("😔 Ничего не найдено. Попробуй написать название по-другому.")
            return

        kb = InlineKeyboardBuilder()
        for r in results:
            emoji = "🎥" if r["type"] == "movie" else "📺"
            kb.row(InlineKeyboardButton(
                text=f"{emoji} {r['title']} ({r['year']})",
                callback_data=f"select:{r['type']}:{r['id']}:{r['title']}"
            ))
        kb.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back"))
        
        await message.answer(f"🔍 Результаты по «<b>{query}</b>»:", reply_markup=kb.as_markup())

    async def cb_select_movie(self, callback):
        if callback.from_user.id != MY_ID:
            return
        
        _, content_type, tmdb_id, title = callback.data.split(":", 3)
        await callback.message.edit_text(f"⏳ Загружаю информацию и ищу видео для «{title}»...")

        session = await self._get_session()
        
        params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
        endpoint = f"{TMDB_BASE}/{'tv' if content_type == 'tv' else 'movie'}/{tmdb_id}"
        overview = "Описание отсутствует."
        poster = None
        
        async with session.get(endpoint, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                overview = data.get("overview", "Описание отсутствует.")[:400]
                if data.get("poster_path"):
                    poster = f"{IMG_BASE}{data['poster_path']}"

        kodik_link = await self._search_kodik(title)

        text = f"🎬 <b>{title}</b>\n\n📝 {overview}"
        kb = InlineKeyboardBuilder()

        if kodik_link:
            import urllib.parse
            safe_link = urllib.parse.quote(kodik_link, safe='')
            web_app_url = f"{PLAYER_URL}?url={safe_link}"
            
            kb.row(InlineKeyboardButton(
                text="▶️ Смотреть в плеере",
                web_app=WebAppInfo(url=web_app_url)
            ))
        else:
            kb.row(InlineKeyboardButton(text="⚠️ Видео пока не найдено", callback_data="noop"))

        kb.row(InlineKeyboardButton(text="◀️ К результатам", callback_data="back"))

        try:
            if poster:
                await callback.message.answer_photo(photo=poster, caption=text, reply_markup=kb.as_markup())
            else:
                await callback.message.answer(text, reply_markup=kb.as_markup())
        except Exception:
            await callback.message.answer(text, reply_markup=kb.as_markup())
            
        await callback.answer()

    async def _search_kodik(self, title: str) -> str:
        """Ищет видео в Kodik и возвращает прямую ссылку на iframe"""
        session = await self._get_session()
        params = {
            "token": KODIK_TOKEN,
            "title": title,
            "with_material_data": "true",
            "limit": 1
        }
        try:
            async with session.get("https://kodik.info/api/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        return results[0].get("link", "")
        except Exception as e:
            logger.error(f"Kodik search error: {e}")
        return ""

    async def cb_back(self, callback):
        if callback.from_user.id != MY_ID:
            return
        await callback.message.delete()
        await self.cmd_start(callback.message)
        await callback.answer()

    async def start(self):
        logger.info("🚀 Бот успешно запущен и работает 24/7!")
        await self.dp.start_polling(self.bot)

    async def stop(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await self.bot.session.close()

if __name__ == "__main__":
    bot = KinoBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        asyncio.run(bot.stop())