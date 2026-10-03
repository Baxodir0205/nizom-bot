from aiogram import Router
from aiogram.types import CallbackQuery, Message

from .. import screen
from ..keyboards import main_menu
from . import reminders, routine, settings, start, today

fallback = Router(name="fallback")


@fallback.message()
async def unknown_message(message: Message, user):
    if not user:
        return await message.answer("Botdan foydalanish uchun /start bosing.")
    # Chat to'lib ketmasligi uchun: foydalanuvchi xabari ham, bizning javob ham tez o'chadi
    await screen.drop(message)
    hint = await message.answer("Pastdagi menyudan tanlang 👇", reply_markup=main_menu)
    screen.delete_later(message.bot, message.chat.id, hint.message_id, 4)


@fallback.callback_query()
async def unknown_callback(call: CallbackQuery, user):
    if not user:
        await call.answer("Avval /start bosing", show_alert=True)
    else:
        await call.answer("Bu tugma eskirgan")


# Tartib muhim: start (bekor qilish, /start) birinchi, fallback oxirida
routers = [
    start.router,
    reminders.router,
    today.router,
    routine.router,
    settings.router,
    fallback,
]
