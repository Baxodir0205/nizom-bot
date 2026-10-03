import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "nizom.db"))
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "Asia/Tashkent").strip() or "Asia/Tashkent"
try:
    ZoneInfo(DEFAULT_TZ)
except Exception:
    raise SystemExit(f"DEFAULT_TZ noto'g'ri: {DEFAULT_TZ!r}. Masalan: Asia/Tashkent")

# Ixtiyoriy: botdan faqat shu Telegram id'lar foydalana oladi (vergul bilan).
# Bo'sh bo'lsa — hamma foydalana oladi.
ALLOWED_USERS = {
    int(x) for x in os.getenv("ALLOWED_USERS", "").replace(" ", "").split(",") if x.isdigit()
}

# Spamdan himoya: THROTTLE_SECONDS ichida THROTTLE_LIMIT dan ko'p amal qilinmaydi
THROTTLE_LIMIT = 30
THROTTLE_SECONDS = 10

# Eslatma tartibi: ish vaqtiga nisbatan qaysi daqiqalarda xabar yuboriladi
# (-5 = 5 daqiqa oldin, 0 = aynan vaqtida, 1 = 1 daqiqa keyin ...).
REMIND_OFFSETS = (-5, 0, 1, 2)
# Har bir xabar necha soniya ko'rinib turadi, keyin o'zi o'chib ketadi
REMIND_VISIBLE = (30, 60, 60, 60)
# Bot o'chiq turgan bo'lsa: shu soniyadan ko'p kechikkan eslatma yuborilmaydi
STALE_SECONDS = 180
# «Bajarildi» xabari necha soniya ko'rinib, keyin o'chadi
DONE_VISIBLE = 3
TICK_SECONDS = 5
