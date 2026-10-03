import html
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAYS_SHORT = ["Du", "Se", "Chor", "Pay", "Ju", "Sha", "Yak"]
MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def norm_title(title: str) -> str:
    """Solishtirish uchun kalit: 'Kitob  O‘qish' va 'kitob o'qish' bir xil."""
    s = " ".join(title.split()).lower()
    for ch in "ʻʼ‘’`´":
        s = s.replace(ch, "'")
    return s


def now_local(tz: str) -> datetime:
    return datetime.now(ZoneInfo(tz))


def today_str(tz: str) -> str:
    return now_local(tz).date().isoformat()


def parse_time(text: str) -> str | None:
    """'7:05', '07.05', '0705', '7 05' -> '07:05'."""
    text = text.strip()
    m = re.fullmatch(r"(\d{1,2})[:.\s]?(\d{2})", text)
    if not m:
        return None
    h, mnt = int(m.group(1)), int(m.group(2))
    if h > 23 or mnt > 59:
        return None
    return f"{h:02d}:{mnt:02d}"


def parse_date(text: str, today: date) -> date | None:
    """'5.10', '05.10.2026', '5/10' -> date. Yil ko'rsatilmasa, eng yaqin kelgusi sana."""
    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?", text.strip())
    if not m:
        return None
    d, mo = int(m.group(1)), int(m.group(2))
    y = m.group(3)
    try:
        if y:
            y = int(y)
            if y < 100:
                y += 2000
            return date(y, mo, d)
        result = date(today.year, mo, d)
        if result < today:
            result = date(today.year + 1, mo, d)
        return result
    except ValueError:
        return None


def to_time(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def combine(d: date, hhmm: str, tz: str) -> datetime:
    return datetime.combine(d, to_time(hhmm), tzinfo=ZoneInfo(tz))


def human_date(d: date, today: date | None = None) -> str:
    text = f"{d.day}-{MONTHS[d.month - 1]}, {WEEKDAYS[d.weekday()].lower()}"
    if today is not None:
        if d == today:
            return f"Bugun, {text}"
        if d == today + timedelta(days=1):
            return f"Ertaga, {text}"
        if d == today - timedelta(days=1):
            return f"Kecha, {text}"
    return text


def days_label(days: str) -> str:
    if days == "0123456":
        return "har kuni"
    if days == "01234":
        return "ish kunlari"
    if days == "56":
        return "dam olish kunlari"
    return ", ".join(WEEKDAYS_SHORT[int(c)] for c in sorted(days))


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    cur = now.time().replace(second=0, microsecond=0)
    s, e = to_time(start), to_time(end)
    if s == e:
        return False
    if s < e:
        return s <= cur < e
    return cur >= s or cur < e  # tun orqali o'tadi, masalan 23:00-07:00


def parse_range(text: str) -> tuple[str, str] | None:
    """'23:00-07:00' -> ('23:00', '07:00')."""
    parts = re.split(r"\s*[-–—]\s*|\s+", text.strip())
    if len(parts) != 2:
        return None
    a, b = parse_time(parts[0]), parse_time(parts[1])
    if not a or not b or a == b:
        return None
    return a, b
