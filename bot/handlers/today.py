from datetime import date, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import db, screen
from ..keyboards import BTN_TODAY, DayCb, ItemCb
from ..middleware import Registered
from ..utils import esc, human_date, now_local

router = Router(name="today")
router.message.filter(Registered())
router.callback_query.filter(Registered())

MARK = {"pending": "⬜", "done": "✅", "skipped": "❌"}


async def day_items(user, d: date) -> list[dict]:
    """Shu kunga to'g'ri keladigan kun tartibi bandlari (vaqt bo'yicha)."""
    statuses = await db.routine_statuses(user["id"], d.isoformat())
    items = [
        {
            "id": r["id"], "title": r["title"], "time": r["time"],
            "status": statuses.get(r["id"], "pending"),
        }
        for r in await db.routines_for_weekday(user["id"], d.weekday())
    ]
    items.sort(key=lambda i: i["time"])
    return items


def _parse_date(text: str) -> date | None:
    try:
        d = date.fromisoformat(text)
    except ValueError:
        return None
    # Juda uzoq sanalarga o'tib ketmaslik (date.max dan oshib xato bermasligi uchun)
    return d if date(2000, 1, 1) <= d <= date(2100, 1, 1) else None


def _label(item: dict) -> str:
    return f"{MARK[item['status']]} {item['time']} {item['title']}"


async def render_day(user, d: date):
    today = now_local(user["tz"]).date()
    items = await day_items(user, d)
    ds = d.isoformat()

    lines = [f"📅 <b>{human_date(d, today)}</b>\n"]
    if not items:
        lines.append("Bu kunga hech narsa rejalashtirilmagan.\n")
        lines.append("🔁 Kun tartibi orqali qo'shing.")
    else:
        for item in items:
            lines.append(esc(_label(item)))
        done = sum(1 for i in items if i["status"] == "done")
        lines.append(f"\nBajarildi: {done}/{len(items)}")
        lines.append("\n<i>Bandni bossangiz, bajarildi deb belgilanadi.</i>")

    b = InlineKeyboardBuilder()
    for item in items:
        b.row(InlineKeyboardButton(
            text=_label(item)[:60],
            callback_data=ItemCb(id=item["id"], date=ds).pack(),
        ))

    prev_d, next_d = (d - timedelta(days=1)).isoformat(), (d + timedelta(days=1)).isoformat()
    nav = [InlineKeyboardButton(text="⬅️", callback_data=DayCb(date=prev_d).pack())]
    if d != today:
        nav.append(InlineKeyboardButton(text="Bugun", callback_data=DayCb(date=today.isoformat()).pack()))
    nav.append(InlineKeyboardButton(text="➡️", callback_data=DayCb(date=next_d).pack()))
    b.row(*nav)

    return "\n".join(lines), b.as_markup()


async def _edit(call: CallbackQuery, user, d: date):
    text, kb = await render_day(user, d)
    await screen.edit(call, text, kb)


@router.message(F.text == BTN_TODAY)
async def today_view(message: Message, state: FSMContext, user):
    await screen.abort(message.bot, message.chat.id, state)
    await screen.drop(message)
    d = now_local(user["tz"]).date()
    text, kb = await render_day(user, d)
    await screen.show(message.bot, user["id"], text, kb)


@router.callback_query(DayCb.filter())
async def day_nav(call: CallbackQuery, callback_data: DayCb, user):
    d = _parse_date(callback_data.date)
    if d is None:
        return await call.answer("Bu tugma eskirgan")
    await _edit(call, user, d)
    await call.answer()


@router.callback_query(ItemCb.filter())
async def item_click(call: CallbackQuery, callback_data: ItemCb, user):
    uid = call.from_user.id
    d = _parse_date(callback_data.date)
    if d is None:
        return await call.answer("Bu tugma eskirgan")
    routine = await db.get_routine(callback_data.id)
    if not routine or routine["user_id"] != uid:
        await call.answer("Topilmadi", show_alert=True)
    else:
        statuses = await db.routine_statuses(uid, callback_data.date)
        cur = statuses.get(routine["id"], "pending")
        new = None if cur != "pending" else "done"
        await db.set_routine_status(routine["id"], callback_data.date, new)
        await call.answer("✅ Bajarildi" if new else "Qaytarildi")

    await _edit(call, user, d)
