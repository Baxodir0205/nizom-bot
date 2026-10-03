import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent, MenuButtonCommands

from bot import config, db, scheduler
from bot.handlers import routers
from bot.middleware import UserMiddleware


async def setup_menu(bot: Bot) -> None:
    """Telegramdagi ko'k «Menu» tugmasi va undagi buyruqlar. Xato bo'lsa, bot to'xtamaydi."""
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Boshlash"),
            BotCommand(command="settings", description="Sozlamalar"),
            BotCommand(command="help", description="Yordam"),
        ])
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        # Telegram serverida haqiqatan nima saqlanganini tekshirib, logga yozamiz
        saved = [f"/{c.command}" for c in await bot.get_my_commands()]
        button = (await bot.get_chat_menu_button()).type
        logging.getLogger(__name__).info("Menu o'rnatildi: tugma=%s, buyruqlar=%s", button, " ".join(saved))
    except Exception:
        logging.getLogger(__name__).exception("Menu buyruqlarini o'rnatib bo'lmadi")


async def on_error(event: ErrorEvent) -> bool:
    """Kutilmagan xato: logga yozamiz, tugma bosilgan bo'lsa «yuklanmoqda» belgisini olib tashlaymiz."""
    log = logging.getLogger("bot.errors")
    log.error("Handlerda xato", exc_info=event.exception)
    call = event.update.callback_query
    if call is not None:
        with contextlib.suppress(Exception):
            await call.answer("Xatolik yuz berdi, qayta urinib ko'ring", show_alert=True)
    return True


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylga BOT_TOKEN=... yozing.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await db.init()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Bot faqat shaxsiy chatda ishlaydi
    dp.message.filter(F.chat.type == ChatType.PRIVATE)
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())
    dp.include_routers(*routers)
    dp.errors.register(on_error)

    await setup_menu(bot)

    reminders = asyncio.create_task(scheduler.run(bot))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminders
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
