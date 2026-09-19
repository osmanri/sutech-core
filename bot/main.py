import asyncio
import logging
import os
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

try:
    from bot_setup import configure_bot_profile
    from config import BOT_TOKEN, USE_WEBHOOK, WEBHOOK_PATH, WEBHOOK_SECRET, WEBHOOK_URL
    from db import init_db
    from handlers.start import start_router
    from handlers.webapp import webapp_router
    from water_balance import CALCULATION_VERSION
except ImportError:
    from bot.bot_setup import configure_bot_profile
    from bot.config import BOT_TOKEN, USE_WEBHOOK, WEBHOOK_PATH, WEBHOOK_SECRET, WEBHOOK_URL
    from bot.db import init_db
    from bot.handlers.start import start_router
    from bot.handlers.webapp import webapp_router
    from bot.water_balance import CALCULATION_VERSION


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logging.getLogger("aiogram").setLevel(logging.INFO)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    """Render and UptimeRobot readiness endpoint; contains no secrets."""
    return web.json_response(
        {
            "status": "ok",
            "service": "su-tech-bot",
            "updates": "webhook" if USE_WEBHOOK else "polling",
            "calculation_version": CALCULATION_VERSION,
            "revision": os.getenv("RENDER_GIT_COMMIT", "local")[:12],
        }
    )


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(webapp_router)
    return dp


async def start_http_server(bot: Bot, dp: Dispatcher) -> web.AppRunner:
    """Open the health and Telegram webhook routes before external API calls."""
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
        handle_in_background=True,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health endpoint is listening on 0.0.0.0:%s", port)
    return runner


async def main() -> None:
    logger.info("Starting Su-Tech bot")
    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()
    runner = await start_http_server(bot, dp)

    try:
        await configure_bot_profile(bot)

        if USE_WEBHOOK:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            webhook = await bot.get_webhook_info()
            logger.info(
                "Telegram webhook active: url=%s pending_updates=%s",
                webhook.url,
                webhook.pending_update_count,
            )
            # aiohttp handles Telegram POST requests until the process is stopped.
            await asyncio.Event().wait()
        else:
            # Local development remains convenient and never competes with the
            # production webhook after deleting it explicitly.
            await bot.delete_webhook(drop_pending_updates=False)
            logger.info("Local polling active")
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                close_bot_session=False,
            )
    finally:
        await runner.cleanup()
        logger.info("Su-Tech bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
