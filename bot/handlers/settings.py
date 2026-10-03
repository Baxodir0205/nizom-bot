from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, screen
from ..keyboards import BTN_SETTINGS, TEXT_INPUT, SetCb, settings_kb
from ..middleware import Registered
from ..utils import parse_range

router = Router(name="settings")
router.message.filter(Registered())
router.callback_query.filter(Registered())


class QuietTime(StatesGroup):
    waiting = State()


def settings_text(user) -> str:
    quiet = "yoqilgan ✅" if user["quiet_on"] else "o'chiq ❌"
    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🔕 Jim rejim: {quiet} ({user['quiet_start']}–{user['quiet_end']})\n\n"
        "<i>Jim rejimda eslatmalar ovozsiz keladi, shuning uchun ular yo'qolmaydi.</i>"
    )


@router.message(Command("settings"))
@router.message(F.text == BTN_SETTINGS)
async def settings_menu(message: Message, state: FSMContext, user):
    await screen.abort(message.bot, message.chat.id, state)
    await screen.drop(message)
    await screen.show(message.bot, user["id"], settings_text(user), settings_kb(user))


@router.callback_query(SetCb.filter())
async def settings_action(call: CallbackQuery, callback_data: SetCb, state: FSMContext, user):
    if callback_data.action == "quiet_on":
        await db.toggle_quiet(call.from_user.id)
        user = await db.get_user(call.from_user.id)
        await screen.edit(call, settings_text(user), settings_kb(user))
    elif callback_data.action == "quiet_time":
        await screen.abort(call.bot, call.from_user.id, state)
        prompt = await call.message.answer("Jim rejim vaqtini yozing, masalan: <code>23:00-07:00</code>")
        await state.set_state(QuietTime.waiting)
        await state.update_data(anchor=call.message.message_id, trash=[prompt.message_id])
    await call.answer()


@router.message(QuietTime.waiting, TEXT_INPUT)
async def quiet_time_input(message: Message, state: FSMContext):
    await screen.trash(state, message.message_id)
    parsed = parse_range(message.text)
    if not parsed:
        err = await message.answer("Tushunmadim. Shu ko'rinishda yozing: <code>23:00-07:00</code>")
        return await screen.trash(state, err.message_id)
    start, end = parsed
    uid = message.from_user.id
    await db.update_user(uid, quiet_start=start, quiet_end=end)
    data = await state.get_data()
    await screen.purge(message.bot, uid, data.get("trash", []))
    await state.clear()
    user = await db.get_user(uid)
    await screen.refresh(message.bot, uid, data.get("anchor"), settings_text(user), settings_kb(user))
