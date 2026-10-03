import asyncio
from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import db, screen
from ..keyboards import BTN_ROUTINE, TEXT_INPUT, DaysCb, RoutCb, days_kb
from ..middleware import Registered
from ..utils import days_label, esc, parse_time

router = Router(name="routine")
router.message.filter(Registered())
router.callback_query.filter(Registered())

MAX_ROUTINES = 40
MAX_TITLE = 100


class AddRoutine(StatesGroup):
    title = State()
    time = State()
    days = State()


# ---------- ro'yxat ----------

async def render_list(uid: int):
    items = await db.routines(uid)
    lines = ["🔁 <b>Kun tartibi</b>\n"]
    if not items:
        lines.append(
            "Hozircha bo'sh. Har kuni takrorlanadigan ishlaringizni qo'shing: "
            "uyg'onish, sport, nonushta, kitob o'qish...\n\n"
            "Belgilangan vaqtda eslatma keladi."
        )
    for r in items:
        pause = "" if r["active"] else " ⏸"
        lines.append(f"<b>{r['time']}</b>  {esc(r['title'])} — <i>{days_label(r['days'])}</i>{pause}")

    b = InlineKeyboardBuilder()
    for r in items:
        pause = "" if r["active"] else "⏸ "
        b.row(InlineKeyboardButton(
            text=f"{pause}{r['time']} {r['title']}"[:60],
            callback_data=RoutCb(action="open", id=r["id"]).pack(),
        ))
    b.row(InlineKeyboardButton(text="➕ Qo'shish", callback_data=RoutCb(action="add").pack()))
    return "\n".join(lines), b.as_markup()


def render_card(r):
    status = "faol ✅" if r["active"] else "to'xtatilgan ⏸"
    text = (
        f"🔁 <b>{esc(r['title'])}</b>\n\n"
        f"⏰ {r['time']}\n"
        f"📆 {days_label(r['days']).capitalize()}\n"
        f"Holati: {status}"
    )
    b = InlineKeyboardBuilder()
    b.button(
        text="⏸ To'xtatish" if r["active"] else "▶️ Yoqish",
        callback_data=RoutCb(action="toggle", id=r["id"]),
    )
    b.button(text="🗑 O'chirish", callback_data=RoutCb(action="del", id=r["id"]))
    b.button(text="⬅️ Orqaga", callback_data=RoutCb(action="list"))
    b.adjust(2, 1)
    return text, b.as_markup()


@router.message(F.text == BTN_ROUTINE)
async def routine_menu(message: Message, state: FSMContext):
    await screen.abort(message.bot, message.chat.id, state)
    await screen.drop(message)
    text, kb = await render_list(message.from_user.id)
    await screen.show(message.bot, message.from_user.id, text, kb)


@router.callback_query(RoutCb.filter())
async def routine_action(call: CallbackQuery, callback_data: RoutCb, state: FSMContext):
    uid = call.from_user.id
    action = callback_data.action

    if action == "list":
        text, kb = await render_list(uid)
        await screen.edit(call, text, kb)
        return await call.answer()

    if action == "add":
        if len(await db.routines(uid)) >= MAX_ROUTINES:
            return await call.answer(f"Ko'pi bilan {MAX_ROUTINES} ta band qo'shish mumkin", show_alert=True)
        await screen.abort(call.bot, uid, state)
        prompt = await call.message.answer("📝 Nima qilasiz? Masalan: Sport, Nonushta, Kitob o'qish")
        await state.set_state(AddRoutine.title)
        # anchor — ro'yxat xabari: dialog tugagach shu joyda yangilanadi
        await state.update_data(anchor=call.message.message_id, trash=[prompt.message_id])
        return await call.answer()

    r = await db.get_routine(callback_data.id)
    if not r or r["user_id"] != uid:
        return await call.answer("Topilmadi", show_alert=True)

    if action == "toggle":
        await db.toggle_routine(r["id"])
        r = await db.get_routine(r["id"])
    elif action == "del":
        b = InlineKeyboardBuilder()
        b.button(text="Ha, o'chirilsin", callback_data=RoutCb(action="delok", id=r["id"]))
        b.button(text="Yo'q", callback_data=RoutCb(action="open", id=r["id"]))
        await screen.edit(
            call, f"<b>{esc(r['title'])}</b> kun tartibidan o'chirilsinmi?", b.as_markup()
        )
        return await call.answer()
    elif action == "delok":
        await db.delete_routine(r["id"])
        text, kb = await render_list(uid)
        await screen.edit(call, text, kb)
        return await call.answer("O'chirildi")

    text, kb = render_card(r)
    await screen.edit(call, text, kb)
    await call.answer()


# ---------- qo'shish: nomi → vaqti → kunlari ----------
# Dialog davomidagi hamma xabar (savollar va javoblar) oxirida o'chiriladi,
# ro'yxat xabari esa joyida yangilanadi.

async def _finish(bot, uid: int, state: FSMContext, notice: str | None = None) -> None:
    data = await state.get_data()
    await screen.purge(bot, uid, data.get("trash", []))
    await state.clear()
    text, kb = await render_list(uid)
    if notice:
        text = f"{notice}\n\n{text}"
    await screen.refresh(bot, uid, data.get("anchor"), text, kb)


@router.message(AddRoutine.title, TEXT_INPUT)
async def add_title(message: Message, state: FSMContext):
    await screen.trash(state, message.message_id)
    title = " ".join(message.text.split())
    if not title:
        err = await message.answer("Nomini yozing, masalan: Sport")
        return await screen.trash(state, err.message_id)
    if len(title) > MAX_TITLE:
        err = await message.answer(f"Juda uzun. {MAX_TITLE} belgidan qisqaroq yozing.")
        return await screen.trash(state, err.message_id)
    await state.update_data(title=title)
    await state.set_state(AddRoutine.time)
    prompt = await message.answer(
        f"⏰ <b>{esc(title)}</b> — soat nechada?\nVaqtni yozing, masalan: <code>06:30</code>"
    )
    await screen.trash(state, prompt.message_id)


@router.message(AddRoutine.time, TEXT_INPUT)
async def add_time(message: Message, state: FSMContext):
    await screen.trash(state, message.message_id)
    time = parse_time(message.text)
    if not time:
        err = await message.answer("Vaqtni tushunmadim. Masalan: <code>06:30</code>")
        return await screen.trash(state, err.message_id)
    data = await state.get_data()
    uid = message.from_user.id
    if await db.find_routine(uid, data["title"], time):
        return await _finish(
            message.bot, uid, state,
            notice=f"ℹ️ <b>{esc(data['title'])}</b> soat {time} da kun tartibingizda allaqachon bor.",
        )
    await state.update_data(time=time, picked=[])
    await state.set_state(AddRoutine.days)
    prompt = await message.answer(
        f"📆 <b>{esc(data['title'])}</b> ({time}) — qaysi kunlari?", reply_markup=days_kb()
    )
    await screen.trash(state, prompt.message_id)


_add_lock = asyncio.Lock()


async def _save(call: CallbackQuery, state: FSMContext, days: str):
    uid = call.from_user.id
    data = await state.get_data()
    title, time = data.get("title"), data.get("time")
    if not title or not time:  # dialog holati yo'qolgan
        await state.clear()
        return await call.answer("Bu tugma eskirgan", show_alert=True)
    # «Tayyor» tugmasi ikki marta tez bosilsa, band ikki marta qo'shilib ketmasin
    async with _add_lock:
        if await db.find_routine(uid, title, time):
            return await call.answer("Bu band allaqachon qo'shilgan")
        if len(await db.routines(uid)) >= MAX_ROUTINES:
            await call.answer(f"Ko'pi bilan {MAX_ROUTINES} ta band qo'shish mumkin", show_alert=True)
            return await _finish(call.bot, uid, state)
        await db.add_routine(uid, title, time, days)
    await call.answer(f"✅ Qo'shildi: {time} {title}"[:190])
    await _finish(call.bot, uid, state)


@router.callback_query(AddRoutine.days, DaysCb.filter())
async def days_button(call: CallbackQuery, callback_data: DaysCb, state: FSMContext):
    value = callback_data.value
    data = await state.get_data()

    selected = {v for v in data.get("picked", []) if v in "0123456"}
    if value == "ok":
        if not selected:
            return await call.answer("Kamida bitta kunni tanlang", show_alert=True)
        return await _save(call, state, "".join(sorted(selected)))
    elif value in tuple("0123456"):
        selected ^= {value}

    await state.update_data(picked=sorted(selected))
    with suppress(TelegramBadRequest):
        await call.message.edit_reply_markup(reply_markup=days_kb(selected))
    await call.answer()
