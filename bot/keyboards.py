from aiogram import F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .utils import WEEKDAYS_SHORT

# ---------- asosiy menyu ----------

BTN_TODAY = "📅 Bugun"
BTN_ROUTINE = "🔁 Kun tartibi"
BTN_SETTINGS = "⚙️ Sozlamalar"  # endi «Menu» ichida (/settings); eski tugma ham ishlaydi
BTN_CANCEL = "❌ Bekor qilish"
MENU_TEXTS = {BTN_TODAY, BTN_ROUTINE, BTN_SETTINGS, BTN_CANCEL}

# Foydalanuvchi yozgan oddiy matn (menyu tugmasi yoki buyruq emas)
TEXT_INPUT = F.text & ~F.text.in_(MENU_TEXTS) & ~F.text.startswith("/")

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_ROUTINE)],
    ],
    resize_keyboard=True,
)

# ---------- callback data ----------

class RemCb(CallbackData, prefix="rem"):
    kind: str  # r = kun tartibi
    id: int
    date: str
    action: str  # done | skip


class DayCb(CallbackData, prefix="day"):
    date: str


class ItemCb(CallbackData, prefix="it"):
    id: int
    date: str


class RoutCb(CallbackData, prefix="rt"):
    action: str  # list | add | open | toggle | del | delok
    id: int = 0


class DaysCb(CallbackData, prefix="dy"):
    value: str  # 0..6 (hafta kuni) | ok


class SetCb(CallbackData, prefix="set"):
    action: str
    value: str = ""


# ---------- klaviaturalar ----------

def reminder_kb(kind: str, item_id: int, date: str):
    b = InlineKeyboardBuilder()
    b.button(text="✅ Bajarildi", callback_data=RemCb(kind=kind, id=item_id, date=date, action="done"))
    b.button(text="❌ O'tkazish", callback_data=RemCb(kind=kind, id=item_id, date=date, action="skip"))
    b.adjust(2)
    return b.as_markup()


def days_kb(selected: set[str] | None = None):
    selected = selected or set()
    b = InlineKeyboardBuilder()
    days = InlineKeyboardBuilder()
    for i, name in enumerate(WEEKDAYS_SHORT):
        mark = "✅" if str(i) in selected else "▫️"
        days.button(text=f"{mark} {name}", callback_data=DaysCb(value=str(i)))
    days.adjust(4, 3)
    b.attach(days)
    label = f"Tayyor ({len(selected)} kun)" if selected else "Tayyor"
    b.row(InlineKeyboardButton(text=label, callback_data=DaysCb(value="ok").pack()))
    return b.as_markup()


def settings_kb(user):
    b = InlineKeyboardBuilder()
    on = "✅" if user["quiet_on"] else "❌"
    b.button(text=f"🔕 Jim rejim: {on}", callback_data=SetCb(action="quiet_on"))
    b.button(text="🕰 Jim vaqtni o'zgartirish", callback_data=SetCb(action="quiet_time"))
    b.adjust(1)
    return b.as_markup()
