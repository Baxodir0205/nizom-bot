# Nizom bot — 1-versiya

Telegram bot: kun tartibi, eslatmalar va jim rejim.

## Ishga tushirish (Ubuntu)

1. Papkaga kiring va virtual muhit yarating:
   ```bash
   cd nizom_bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Tokenni yozing:
   ```bash
   cp .env.example .env
   nano .env        # BOT_TOKEN=123456:ABC... deb yozing
   ```
3. Botni ishga tushiring:
   ```bash
   python main.py
   ```
4. Telegramda botga `/start` yozing.

## 24/7 ishlatish (systemd)

Eslatmalar kelishi uchun bot doim yoqiq turishi kerak.

1. `nizom-bot.service` ichidagi `USER` va yo'llarni o'zingiznikiga almashtiring.
2. O'rnating:
   ```bash
   sudo cp nizom-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now nizom-bot
   journalctl -u nizom-bot -f     # loglarni ko'rish
   ```

## Nima qila oladi

| Bo'lim | Vazifasi |
|---|---|
| 📅 Bugun | Bugungi kun tartibi bitta jadvalda. Bandni bossangiz, bajarildi deb belgilanadi. ⬅️ ➡️ bilan boshqa kunlarni ko'rish mumkin. |
| 🔁 Kun tartibi | Takrorlanadigan ishlar: har kuni, ish kunlari, dam olish kunlari yoki tanlangan kunlar. Nomi → vaqti → kunlari ketma-ket so'raladi; kunlar hafta kunlarini belgilab tanlanadi. To'xtatib qo'yish va o'chirish mumkin. |
| ⚙️ Sozlamalar | Jim rejim va uning vaqti. Telegramdagi «Menu» tugmasi ichida yoki `/settings` buyrug'i bilan ochiladi. |

**Chat toza turadi:**
- Botga `/start` yozsangiz, bugungi kun tartibi jadvali chiqadi.
- Pastdagi tugmalar (Bugun, Kun tartibi) yangi ekran ochadi, eskisi o'chadi. Chatda doim bitta jadval turadi.
- Kun tartibiga ish qo'shganingizda savollar va javoblaringiz hammasi o'chadi, jadval joyida yangilanadi.
- Dialog o'rtasida boshqa tugmani bossangiz, yarim qolgan yozishmalar ham o'chadi.

**Eslatmalar qanday keladi** (masalan, Nonushta 06:30 da):
- **06:25** — «Nonushta, 5 daqiqadan keyin» xabari. 30 soniyadan keyin o'zi o'chadi.
- **06:30** — «Nonushta, hozir» xabari. 1 daqiqa turib, o'zi o'chadi.
- Belgilanmasa, har daqiqada yangisi keladi: **06:31** va **06:32** (jami 3 ta, har biri 1 daqiqa turadi).
- Xabarda **✅ Bajarildi** va **❌ O'tkazish** tugmalari bor. Birini bossangiz, qisqa tasdiq ko'rinib (3 soniya) xabar o'chadi va qolgan eslatmalar kelmaydi.
- Hammasi belgilanmasa, band «bajarilmadi» (❌) deb belgilanadi.
- Shunday qilib chatda eslatmalar to'planib qolmaydi.
- Vaqtlarni `bot/config.py` dagi `REMIND_OFFSETS` (daqiqa) va `REMIND_VISIBLE` (soniya) bilan o'zgartirish mumkin.

**Jim rejim:** belgilangan soatlarda eslatmalar **ovozsiz** keladi.

## Xavfsizlik va ma'lumotlar

- Har bir foydalanuvchi faqat o'z yozuvlarini ko'radi va o'zgartiradi: har bir tugma bosilganda band egasi tekshiriladi, boshqa odamning bandiga tegib bo'lmaydi.
- `ALLOWED_USERS=id1,id2` (`.env`) bilan botni faqat o'zingiz tanlagan odamlarga ochish mumkin. Bo'sh bo'lsa — hamma foydalana oladi.
- Spamdan himoya: 10 soniyada 30 tadan ko'p bosish/xabar e'tiborga olinmaydi.
- Bot faqat shaxsiy chatda ishlaydi; matnlar HTML'dan tozalanadi (`<b>` kabi belgilar buzmaydi).
- Baza fayli (`nizom.db`) faqat egasi o'qiy oladigan qilib yaratiladi. Token faqat `.env` da turadi; `.env` va `*.db` `.gitignore` da.
- Kutilmagan xato bo'lsa, bot to'xtamaydi: logga yozadi va tugmadagi «yuklanmoqda» belgisini olib tashlaydi.

## Texnik tafsilotlar

- **aiogram 3 + SQLite** (`nizom.db`). Hamma holat bazada saqlanadi.
- **Eslatmalar:** `bot/scheduler.py` har 5 soniyada bazani tekshiradi. Holat bazada saqlanadi: bot qayta ishga tushsa, ko'rinib turgan eslatma xabarlari o'chiriladi. Bot o'chiq paytda o'tib ketgan va 3 daqiqadan ko'p kechikkan eslatma yuborilmaydi.
- **Vaqt mintaqasi:** Asia/Tashkent (`.env` da `DEFAULT_TZ` bilan o'zgartirish mumkin).
- **Holat (FSM):** xotirada saqlanadi. Bot qayta ishga tushsa, faqat yarim qolgan dialog (masalan, kun tartibiga ish qo'shish) bekor bo'ladi.

## Tuzilishi

```
main.py              ishga tushirish
bot/
  config.py          .env sozlamalari
  db.py              SQLite jadvallari va so'rovlar
  scheduler.py       eslatmalar tsikli
  keyboards.py       tugmalar va callback'lar
  screen.py          chatni toza saqlash (ekran xabari, yozishmalarni o'chirish)
  utils.py           sana/vaqt yordamchilari
  middleware.py      foydalanuvchini yuklash, ro'yxatdan o'tganlik filtri
  handlers/          start, today, routine, settings, reminders
```

## 2-versiya rejasi

Sport va ovqatlanish rejasi, suv va uyqu rejimi, progress grafigi.
