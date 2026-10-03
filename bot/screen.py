"""Chatni toza saqlash.

• Har bir foydalanuvchida bitta asosiy «ekran» xabari bor (Bugun, Kun tartibi, Sozlamalar).
  Yangi ekran ochilganda eskisi o'chiriladi.
• Dialog (masalan, kun tartibiga ish qo'shish) davomidagi barcha yordamchi xabarlar
  (savollar va foydalanuvchi javoblari) FSM ma'lumotidagi «trash» ro'yxatida yig'iladi
  va dialog tugagach hammasi o'chiriladi — chatda faqat ekran qoladi.
"""

import asyncio
import logging
from collections import defaultdict
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from . import db

log = logging.getLogger(__name__)

# Bir foydalanuvchi uchun «ekran» amallari ketma-ket bajariladi (ikki marta tez bosilsa,
# chatda ikkita ekran qolib ketmasligi uchun)
_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

# Eslatma uchun: vaqtinchalik xabarlarni o'chiradigan fon vazifalari
_bg: set[asyncio.Task] = set()


async def delete(bot: Bot, chat_id: int, message_id: int) -> None:
    # Tarmoq xatosi yoki eski xabar — chatni tozalash muhim emas, asosiy ish to'xtamasin
    with suppress(TelegramAPIError):
        await bot.delete_message(chat_id, message_id)


async def purge(bot: Bot, chat_id: int, ids: list[int]) -> None:
    for mid in dict.fromkeys(ids):
        await delete(bot, chat_id, mid)


async def drop(message: Message) -> None:
    """Foydalanuvchining o'zi yuborgan xabarni (menyu tugmasi, buyruq) o'chirish."""
    await delete(message.bot, message.chat.id, message.message_id)


def delete_later(bot: Bot, chat_id: int, message_id: int, seconds: float) -> None:
    """Xabarni birozdan keyin o'chirish (fon vazifasi)."""
    async def _job() -> None:
        await asyncio.sleep(seconds)
        await delete(bot, chat_id, message_id)

    task = asyncio.create_task(_job())
    _bg.add(task)
    task.add_done_callback(_bg.discard)


async def trash(state: FSMContext, *message_ids: int) -> None:
    """Dialog tugaganda o'chiriladigan xabarlarni ro'yxatga qo'shish."""
    data = await state.get_data()
    await state.update_data(trash=[*data.get("trash", []), *message_ids])


async def abort(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Yarim qolgan dialogni to'xtatish: yordamchi xabarlarni o'chirib, holatni tozalash."""
    data = await state.get_data()
    await purge(bot, chat_id, data.get("trash", []))
    await state.clear()


async def show(bot: Bot, uid: int, text: str, markup=None) -> Message | None:
    """Yangi ekranni pastga yuborish; eski ekran xabari o'chiriladi."""
    async with _locks[uid]:
        user = await db.get_user(uid)
        if user and user["screen_msg"]:
            await delete(bot, uid, user["screen_msg"])
        sent = await bot.send_message(uid, text, reply_markup=markup)
        await db.update_user(uid, screen_msg=sent.message_id)
        return sent


async def refresh(bot: Bot, uid: int, message_id: int | None, text: str, markup=None) -> None:
    """Ekranni joyida yangilash; xabar topilmasa, yangisini yuborish."""
    if message_id:
        try:
            await bot.edit_message_text(text, chat_id=uid, message_id=message_id, reply_markup=markup)
            await db.update_user(uid, screen_msg=message_id)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
    await show(bot, uid, text, markup)


async def edit(call: CallbackQuery, text: str, markup=None) -> None:
    """Tugma bosilganda ekranni joyida yangilash. Matn o'zgarmagan bo'lsa — jim o'tadi,
    xabar o'chib ketgan bo'lsa — ekranni qaytadan yuboradi."""
    msg = call.message
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as e:
        if "not modified" in str(e):
            return
        log.info("Xabarni tahrirlab bo'lmadi (%s): %s", call.from_user.id, e)
        await show(call.bot, call.from_user.id, text, markup)
