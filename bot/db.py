"""SQLite bilan ishlash. Barcha holat shu yerda saqlanadi, shuning uchun
bot qayta ishga tushsa ham vazifalar va eslatmalar yo'qolmaydi."""

import contextlib
import os
from datetime import datetime, timezone

import aiosqlite

from .config import DB_PATH, DEFAULT_TZ
from .utils import norm_title

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    name          TEXT,
    tz            TEXT NOT NULL DEFAULT 'Asia/Tashkent',
    quiet_on      INTEGER NOT NULL DEFAULT 0,
    quiet_start   TEXT NOT NULL DEFAULT '23:00',
    quiet_end     TEXT NOT NULL DEFAULT '07:00',
    created_at    TEXT NOT NULL,
    screen_msg    INTEGER,                 -- chatdagi asosiy («ekran») xabar id'si
    menu_msg      INTEGER                  -- pastki panelni o'rnatgan xabar id'si
);

CREATE TABLE IF NOT EXISTS routines (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    title      TEXT NOT NULL,
    time       TEXT NOT NULL,          -- HH:MM
    days       TEXT NOT NULL,          -- '0123456' (0 = dushanba)
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routine_log (
    routine_id INTEGER NOT NULL,
    date       TEXT NOT NULL,
    status     TEXT NOT NULL,          -- done | skipped
    PRIMARY KEY (routine_id, date)
);

-- Eslatma jarayoni: har bir ish uchun har kuni bitta qator
CREATE TABLE IF NOT EXISTS reminders (
    routine_id INTEGER NOT NULL,
    date       TEXT NOT NULL,
    user_id    INTEGER NOT NULL,
    step       INTEGER NOT NULL DEFAULT 0,   -- nechta bosqich o'tdi
    sent       INTEGER NOT NULL DEFAULT 0,   -- nechta xabar haqiqatan yuborildi
    msg_id     INTEGER,                      -- hozir ko'rinib turgan xabar
    delete_at  TEXT,                         -- uni o'chirish vaqti (UTC ISO)
    finished   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (routine_id, date)
);
"""

USER_FIELDS = {"name", "tz", "quiet_on", "quiet_start", "quiet_end", "screen_msg", "menu_msg"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def init() -> None:
    global _db
    # Baza fayli faqat egasi o'qiy olsin (boshqa kompyuter foydalanuvchilari ko'rmasin)
    old_umask = os.umask(0o077)
    try:
        _db = await aiosqlite.connect(DB_PATH)
    finally:
        os.umask(old_umask)
    with contextlib.suppress(OSError):
        os.chmod(DB_PATH, 0o600)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.executescript(SCHEMA)
    # Eski bazalar uchun: users jadvaliga yangi ustunlarni qo'shish
    cols = [r["name"] for r in await _all("PRAGMA table_info(users)")]
    for col in ("screen_msg", "menu_msg"):
        if col not in cols:
            await _db.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER")
    await _db.commit()


async def close() -> None:
    if _db is not None:
        await _db.close()


async def _one(sql: str, params: tuple = ()) -> aiosqlite.Row | None:
    async with _db.execute(sql, params) as cur:
        return await cur.fetchone()


async def _all(sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
    async with _db.execute(sql, params) as cur:
        return list(await cur.fetchall())


async def _run(sql: str, params: tuple = ()) -> int:
    cur = await _db.execute(sql, params)
    await _db.commit()
    return cur.lastrowid


# ---------- users ----------

async def get_user(uid: int):
    return await _one("SELECT * FROM users WHERE id = ?", (uid,))


async def create_user(uid: int, name: str) -> None:
    await _run(
        "INSERT OR IGNORE INTO users (id, name, tz, created_at) VALUES (?, ?, ?, ?)",
        (uid, name, DEFAULT_TZ, _now()),
    )


async def update_user(uid: int, **fields) -> None:
    bad = set(fields) - USER_FIELDS
    if bad:
        raise ValueError(f"Noma'lum maydon: {bad}")
    cols = ", ".join(f"{k} = ?" for k in fields)
    await _run(f"UPDATE users SET {cols} WHERE id = ?", (*fields.values(), uid))


async def toggle_quiet(uid: int) -> None:
    """Jim rejimni bir SQL amalida almashtirish (ikki marta tez bosilsa ham adashmaydi)."""
    await _run("UPDATE users SET quiet_on = 1 - quiet_on WHERE id = ?", (uid,))


async def all_users():
    return await _all("SELECT * FROM users")


# ---------- routines (kun tartibi) ----------

async def add_routine(uid: int, title: str, time: str, days: str) -> int:
    return await _run(
        "INSERT INTO routines (user_id, title, time, days, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, title, time, days, _now()),
    )


async def get_routine(rid: int):
    return await _one("SELECT * FROM routines WHERE id = ?", (rid,))


async def routines(uid: int):
    return await _all(
        "SELECT * FROM routines WHERE user_id = ? ORDER BY time, id", (uid,)
    )


async def routines_for_weekday(uid: int, weekday: int):
    rows = await _all(
        "SELECT * FROM routines WHERE user_id = ? AND active = 1 ORDER BY time, id",
        (uid,),
    )
    return [r for r in rows if str(weekday) in r["days"]]


async def toggle_routine(rid: int) -> None:
    await _run("UPDATE routines SET active = 1 - active WHERE id = ?", (rid,))


async def delete_routine(rid: int) -> None:
    await _run("DELETE FROM routines WHERE id = ?", (rid,))
    await _run("DELETE FROM routine_log WHERE routine_id = ?", (rid,))


async def find_routine(uid: int, title: str, time: str):
    """Shu nom va vaqtdagi mavjud ish (takrorlanmasligi uchun)."""
    key = norm_title(title)
    for r in await _all("SELECT * FROM routines WHERE user_id = ? AND time = ?", (uid, time)):
        if norm_title(r["title"]) == key:
            return r
    return None


async def routine_statuses(uid: int, date: str) -> dict[int, str]:
    rows = await _all(
        "SELECT l.routine_id, l.status FROM routine_log l "
        "JOIN routines r ON r.id = l.routine_id WHERE r.user_id = ? AND l.date = ?",
        (uid, date),
    )
    return {r["routine_id"]: r["status"] for r in rows}


async def set_routine_status(rid: int, date: str, status: str | None) -> None:
    if status is None:
        await _run(
            "DELETE FROM routine_log WHERE routine_id = ? AND date = ?", (rid, date)
        )
    else:
        await _run(
            "INSERT OR REPLACE INTO routine_log (routine_id, date, status) VALUES (?, ?, ?)",
            (rid, date, status),
        )


# ---------- eslatma jarayoni ----------

async def get_reminder(rid: int, date: str):
    return await _one("SELECT * FROM reminders WHERE routine_id = ? AND date = ?", (rid, date))


async def save_reminder(
    rid: int, date: str, uid: int, step: int, sent: int,
    msg_id: int | None, delete_at: datetime | None, finished: bool,
) -> None:
    await _run(
        "INSERT INTO reminders (routine_id, date, user_id, step, sent, msg_id, delete_at, finished) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(routine_id, date) DO UPDATE SET "
        "step = excluded.step, sent = excluded.sent, msg_id = excluded.msg_id, "
        "delete_at = excluded.delete_at, finished = excluded.finished",
        (rid, date, uid, step, sent, msg_id,
         delete_at.isoformat(timespec="seconds") if delete_at else None, int(finished)),
    )


async def expired_reminder_messages(now_utc: datetime):
    return await _all(
        "SELECT * FROM reminders WHERE msg_id IS NOT NULL AND delete_at <= ?",
        (now_utc.isoformat(timespec="seconds"),),
    )


async def clear_reminder_msg(rid: int, date: str) -> None:
    await _run(
        "UPDATE reminders SET msg_id = NULL, delete_at = NULL WHERE routine_id = ? AND date = ?",
        (rid, date),
    )


async def cleanup_reminders(before_date: str) -> None:
    await _run("DELETE FROM reminders WHERE date < ? AND msg_id IS NULL", (before_date,))
