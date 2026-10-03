import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, InaccessibleMessage, Message, TelegramObject

from . import config, db


class UserMiddleware(BaseMiddleware):
    """Har bir xabar/tugma uchun:
    • ruxsat etilmagan foydalanuvchilarni (ALLOWED_USERS) to'xtatadi;
    • spamni cheklaydi;
    • foydalanuvchini bazadan olib, data['user'] ga qo'yadi.
    Har bir foydalanuvchi faqat o'z yozuvlari bilan ishlaydi: id Telegramdan keladi,
    qolgan hamma so'rov shu id bo'yicha yoziladi."""

    def __init__(self) -> None:
        self._hits: defaultdict[int, deque[float]] = defaultdict(deque)

    def _throttled(self, uid: int) -> bool:
        now = time.monotonic()
        hits = self._hits[uid]
        while hits and now - hits[0] > config.THROTTLE_SECONDS:
            hits.popleft()
        if len(hits) >= config.THROTTLE_LIMIT:
            return True
        hits.append(now)
        if len(self._hits) > 5000:  # xotira to'lib ketmasligi uchun eskilarini tozalash
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > config.THROTTLE_SECONDS]:
                del self._hits[k]
        return False

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return None

        if config.ALLOWED_USERS and tg_user.id not in config.ALLOWED_USERS:
            if isinstance(event, CallbackQuery):
                await event.answer("Bu botdan foydalanishga ruxsat yo'q", show_alert=True)
            elif isinstance(event, Message):
                await event.answer("Bu botdan foydalanishga ruxsat yo'q.")
            return None

        if self._throttled(tg_user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Sekinroq 🙂")
            return None

        if isinstance(event, CallbackQuery):
            # Tugma bosilgan xabar o'chgan/eskirgan yoki shaxsiy chat emas bo'lsa — ishlamaymiz
            msg = event.message
            if msg is None or isinstance(msg, InaccessibleMessage) or msg.chat.id != tg_user.id:
                await event.answer("Bu tugma eskirgan")
                return None

        data["user"] = await db.get_user(tg_user.id)
        return await handler(event, data)


class Registered(Filter):
    """Faqat /start bosgan foydalanuvchilar uchun."""

    async def __call__(self, event: TelegramObject, user=None) -> bool:
        return user is not None
