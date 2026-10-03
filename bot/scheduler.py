"""Eslatmalar tsikli.

Har bir kun tartibi bandi uchun uch marta xabar yuboriladi (config.REMIND_OFFSETS):
vaqtidan 5 daqiqa oldin, aynan vaqtida va 5 daqiqa keyin. Har bir xabar bir necha
soniya ko'rinib turadi, keyin o'zi o'chadi (chat to'lib ketmasligi uchun).

  • ✅ Bajarildi / ❌ O'tkazish bosilsa — qisqa tasdiq ko'rinib, xabar o'chadi,
    qolgan eslatmalar to'xtaydi.
  • Uchala xabar ham belgilanmasa — band «bajarilmadi» (❌) deb belgilanadi.

Hamma holat bazada (reminders jadvali), shuning uchun bot qayta ishga tushsa ham
ko'rinib turgan xabarlar o'chiriladi va jarayon davom etadi. Bot o'chiq paytda
o'tib ketgan eslatma STALE_SECONDS dan ko'p kechiksa, yuborilmaydi.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from . import db
from .config import REMIND_OFFSETS, REMIND_VISIBLE, STALE_SECONDS, TICK_SECONDS
from .keyboards import reminder_kb
from .utils import combine, esc, in_quiet_hours, utcnow

log = logging.getLogger(__name__)

STEPS = len(REMIND_OFFSETS)


# ---------- matnlar ----------

def _when(offset: int) -> str:
    if offset < 0:
        return f"{-offset} daqiqadan keyin"
    if offset == 0:
        return "hozir"
    return f"{offset} daqiqa o'tdi"


def reminder_text(title: str, time: str, step: int) -> str:
    return f"⏰ <b>{esc(title)}</b>\n🕐 {time} — {_when(REMIND_OFFSETS[step])}"


# ---------- Telegram bilan ishlash ----------

async def send(bot: Bot, chat_id: int, text: str, silent: bool, markup) -> tuple[str, int | None]:
    """("ok", xabar_id) | ("retry", None) — keyinroq qayta urinish | ("drop", None) — yuborib bo'lmaydi."""
    try:
        msg = await bot.send_message(chat_id, text, reply_markup=markup, disable_notification=silent)
        return "ok", msg.message_id
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return "retry", None
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        log.info("Foydalanuvchi %s ga yuborib bo'lmadi: %s", chat_id, e)
        return "drop", None
    except Exception as e:
        log.warning("Yuborishda xato (%s): %s", chat_id, e)
        return "retry", None


async def delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        pass  # allaqachon o'chirilgan yoki juda eski
    except Exception as e:
        log.warning("Xabarni o'chirib bo'lmadi (%s): %s", chat_id, e)


# ---------- bitta ish uchun jarayon ----------

async def _handle(bot: Bot, user, r, d: date, marked: dict, now: datetime, now_utc: datetime, quiet: bool):
    uid, tz, ds, rid = user["id"], user["tz"], d.isoformat(), r["id"]
    st = await db.get_reminder(rid, ds)
    if st and st["finished"]:
        return

    if rid in marked:  # «Bugun» ro'yxatida yoki tugma orqali belgilangan
        if st:
            if st["msg_id"]:
                await delete_message(bot, uid, st["msg_id"])
            await db.save_reminder(rid, ds, uid, STEPS, st["sent"], None, None, True)
        return

    if st and st["msg_id"]:
        return  # xabar ko'rinib turibdi, uni o'chirishni tick() bajaradi

    step = st["step"] if st else 0
    sent = st["sent"] if st else 0
    base = combine(d, r["time"], tz)
    skipped_any = False

    while step < STEPS:
        at = base + timedelta(minutes=REMIND_OFFSETS[step])
        if now < at:
            break
        if now >= at + timedelta(seconds=STALE_SECONDS):
            step += 1  # bot o'chiq edi, bu bosqich o'tib ketgan
            skipped_any = True
            continue

        status, mid = await send(
            bot, uid, reminder_text(r["title"], r["time"], step), quiet, reminder_kb("r", rid, ds)
        )
        if status == "retry":
            return
        if status == "ok":
            hide_at = now_utc + timedelta(seconds=REMIND_VISIBLE[step])
            await db.save_reminder(rid, ds, uid, step + 1, sent + 1, mid, hide_at, False)
        else:
            await db.save_reminder(rid, ds, uid, step + 1, sent, None, None, False)
        return

    if step >= STEPS:
        # Uchala xabar ham yuborilib, hech biri belgilanmagan bo'lsa — bajarilmadi
        if sent >= STEPS:
            await db.set_routine_status(rid, ds, "skipped")
        if st or sent:
            await db.save_reminder(rid, ds, uid, step, sent, None, None, True)
    elif skipped_any and st:
        await db.save_reminder(rid, ds, uid, step, sent, None, None, False)


async def process_user(bot: Bot, user, now_utc: datetime) -> None:
    uid, tz = user["id"], user["tz"]
    now = now_utc.astimezone(ZoneInfo(tz))
    quiet = bool(user["quiet_on"]) and in_quiet_hours(now, user["quiet_start"], user["quiet_end"])
    today = now.date()
    # Kecha va ertaga ham: yarim tundan o'tadigan eslatmalar uchun (masalan, 00:02 dagi ish)
    for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
        marked = await db.routine_statuses(uid, d.isoformat())
        for r in await db.routines_for_weekday(uid, d.weekday()):
            await _handle(bot, user, r, d, marked, now, now_utc, quiet)


async def tick(bot: Bot, now_utc: datetime | None = None) -> None:
    now_utc = now_utc or utcnow()
    # 1) Vaqti o'tgan xabarlarni o'chirish
    for row in await db.expired_reminder_messages(now_utc):
        await delete_message(bot, row["user_id"], row["msg_id"])
        await db.clear_reminder_msg(row["routine_id"], row["date"])
    # 2) Yangi eslatmalarni yuborish
    for user in await db.all_users():
        try:
            await process_user(bot, user, now_utc)
        except Exception:
            log.exception("Foydalanuvchi %s uchun eslatmalarda xato", user["id"])


async def run(bot: Bot) -> None:
    log.info("Eslatmalar tsikli ishga tushdi")
    last_cleanup: date | None = None
    while True:
        try:
            await tick(bot)
            today = utcnow().date()
            if last_cleanup != today:
                await db.cleanup_reminders((today - timedelta(days=3)).isoformat())
                last_cleanup = today
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Eslatmalar tsiklida xato")
        await asyncio.sleep(TICK_SECONDS)
