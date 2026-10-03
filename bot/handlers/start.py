from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import db, screen
from ..keyboards import BTN_CANCEL, main_menu
from ..utils import esc, now_local
from .today import render_day

router = Router(name="start")

HELP_TEXT = (
    "<b>Nizom bot</b> — kun tartibingiz yordamchisi.\n\n"
    "📅 <b>Bugun</b> — bugungi reja. Bandni bossangiz, bajarilgan deb belgilanadi.\n"
    "🔁 <b>Kun tartibi</b> — har kuni (yoki tanlangan kunlarda) takrorlanadigan ishlar: "
    "uyg'onish, sport, ovqat, kitob...\n"
    "⚙️ <b>Sozlamalar</b> — jim rejim. «Menu» tugmasi ichida yoki /settings.\n\n"
    "Eslatma kelganda: ✅ Bajarildi / ❌ O'tkazish."
)


async def send_menu(message: Message, text: str) -> None:
    """Pastki panelni (main_menu) o'rnatuvchi xabar. Oldingisi o'chiriladi, xabarlar to'planmaydi."""
    uid = message.from_user.id
    user = await db.get_user(uid)
    old = user["menu_msg"] if user else None
    sent = await message.answer(text, reply_markup=main_menu)
    if user:
        await db.update_user(uid, menu_msg=sent.message_id)
        if old:
            await screen.delete(message.bot, uid, old)


async def show_today(message: Message) -> None:
    """Bugungi kun tartibi jadvalini asosiy ekran sifatida ko'rsatish."""
    user = await db.get_user(message.from_user.id)
    text, kb = await render_day(user, now_local(user["tz"]).date())
    await screen.show(message.bot, user["id"], text, kb)


@router.message(F.text == BTN_CANCEL)
@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext, user):
    await screen.abort(message.bot, message.chat.id, state)
    await screen.drop(message)
    if user:
        await send_menu(message, "Bekor qilindi.")
        await show_today(message)
    else:
        await message.answer("Bekor qilindi. Boshlash uchun /start bosing.")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, user):
    await screen.abort(message.bot, message.chat.id, state)
    await screen.drop(message)
    name = esc(message.from_user.first_name)
    if user:
        await send_menu(message, f"Qaytganingizdan xursandman, {name}! 👋")
    else:
        await db.create_user(message.from_user.id, message.from_user.full_name)
        await send_menu(
            message,
            f"Assalomu alaykum, {name}! 👋\n\n"
            "Men kun tartibingizni tuzish va uni o'z vaqtida eslatishga yordam beraman.\n\n"
            + HELP_TEXT,
        )
    await show_today(message)


@router.message(Command("help"))
async def help_cmd(message: Message, user):
    await screen.drop(message)
    if user:
        await screen.show(message.bot, user["id"], HELP_TEXT)
    else:
        await message.answer(HELP_TEXT)
