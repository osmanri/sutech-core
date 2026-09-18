import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers.start import start_router
from handlers.webapp import webapp_router
from db import init_db

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


from aiohttp import web

# ─── Health Check Server ──────────────────────────────────────────────────────
async def health_check(request):
    return web.Response(text="200 OK (Health Check)", status=200)


async def start_health_server() -> web.AppRunner:
    """Open Render's HTTP port before any external API request can delay startup."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("🌐 Health-check сервер запущен на 0.0.0.0:%s", port)
    return runner

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

    # Инициализация базы данных SQLite
    init_db()

    # Render считает сервис готовым только после открытия PORT. Запускаем HTTP
    # endpoint до первого сетевого обращения к Telegram, которое может задержаться.
    runner = await start_health_server()
    try:
        # Удаляем накопившиеся апдейты до старта
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Бот запущен. Нажмите Ctrl+C для остановки.")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await runner.cleanup()
        logger.info("🛑 Сессия закрыта. Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал завершения. До свидания!")
