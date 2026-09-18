import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers.start import start_router
from handlers.webapp import webapp_router

# ─── Логирование ──────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
# Приглушаем шумные библиотеки, оставляем DEBUG только для нашего кода
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ─── Точка входа ──────────────────────────────────────────────────────────────
async def main() -> None:
    logger.info("🚀 Запуск АгроБота...")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Регистрируем роутеры в порядке приоритета
    dp.include_router(start_router)
    dp.include_router(webapp_router)

    # Удаляем накопившиеся апдейты до старта
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("✅ Бот запущен. Нажмите Ctrl+C для остановки.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Сессия закрыта. Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал завершения. До свидания!")
