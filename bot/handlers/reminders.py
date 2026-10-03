from contextlib import suppress
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from .. import db
from ..config import DONE_VISIBLE, REMIND_OFFSETS
from ..keyboards import RemCb
from ..middleware import Registered
from ..utils import esc, utcnow

router = Router(name="reminders")
router.callback_query.filter(Registered())

RESULT = {
    "done": ("✅ Bajarildi", "done"),
    "skip": ("❌ O'tkazib yuborildi", "skipped"),
}


@router.callback_query(RemCb.filter())
async def reminder_action(call: CallbackQuery, callback_data: RemCb):
    uid = call.from_user.id
    rid, date, action = callback_data.id, callback_data.date, callback_data.action

    if callback_data.kind != "r" or action not in RESULT:
        with suppress(TelegramBadRequest):
            await call.message.delete()
        return await call.answer()

    routine = await db.get_routine(rid)
    if not routine or routine["user_id"] != uid:
        with suppress(TelegramBadRequest):
            await call.message.delete()
        return await call.answer("Bu band o'chirilgan", show_alert=True)

    try:
        date_ok = bool(datetime.strptime(date, "%Y-%m-%d"))
    except ValueError:
        date_ok = False
    if not date_ok:
        return await call.answer("Bu tugma eskirgan")

    label, status = RESULT[action]
    await db.set_routine_status(rid, date, status)

    # Qisqa tasdiq ko'rsatamiz, so'ng xabar o'zi o'chadi (scheduler.tick)
    st = await db.get_reminder(rid, date)
    await db.save_reminder(
        rid, date, uid, len(REMIND_OFFSETS), st["sent"] if st else 1,
        call.message.message_id, utcnow() + timedelta(seconds=DONE_VISIBLE), True,
    )
    with suppress(TelegramBadRequest):
        await call.message.edit_text(f"{label}: <b>{esc(routine['title'])}</b>", reply_markup=None)
    await call.answer(label)
