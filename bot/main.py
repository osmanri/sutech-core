import asyncio
import json
import logging
import os
import sys
import time
from datetime import timezone
from types import SimpleNamespace

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from aiogram.utils.web_app import safe_parse_webapp_init_data
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

try:
    from bot_setup import configure_bot_profile
    from config import BOT_TOKEN, USE_WEBHOOK, WEBHOOK_PATH, WEBHOOK_SECRET, WEBHOOK_URL
    from db import init_db, check_db_health
    from handlers.start import start_router
    from handlers.fields import fields_router
    from handlers.webapp import webapp_router, handle_webapp_data
    from water_balance import CALCULATION_VERSION
    from daily_monitor import run_daily_monitor
    from i18n import t
    from user_state import get_lang
except ImportError:
    from bot.bot_setup import configure_bot_profile
    from bot.config import BOT_TOKEN, USE_WEBHOOK, WEBHOOK_PATH, WEBHOOK_SECRET, WEBHOOK_URL
    from bot.db import init_db, check_db_health
    from bot.handlers.start import start_router
    from bot.handlers.fields import fields_router
    from bot.handlers.webapp import webapp_router, handle_webapp_data
    from bot.water_balance import CALCULATION_VERSION
    from bot.daily_monitor import run_daily_monitor
    from bot.i18n import t
    from bot.user_state import get_lang


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
BOT_APP_KEY = web.AppKey("su_tech_bot", Bot)

WEBAPP_ORIGINS = {
    "https://frontend-2-mauve.vercel.app",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
}


@web.middleware
async def webapp_cors(request: web.Request, handler):
    if request.path != "/api/analyze":
        return await handler(request)
    origin = request.headers.get("Origin")
    if origin and origin not in WEBAPP_ORIGINS:
        raise web.HTTPForbidden()
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = exc
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


async def analyze_webapp(request: web.Request) -> web.Response:
    """Deliver a Mini App calculation to its signed-in Telegram user.

    Inline and menu Mini Apps cannot use Telegram.WebApp.sendData. Their signed
    initData identifies the user without trusting a browser-supplied user ID.
    """
    raw = await request.content.read(8193)
    if len(raw) > 8192:
        raise web.HTTPRequestEntityTooLarge(max_size=8192, actual_size=len(raw))
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise web.HTTPBadRequest(text="Invalid JSON") from None
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Invalid request")
    init_data, payload = body.get("init_data"), body.get("payload")
    if not isinstance(init_data, str) or not init_data or len(init_data) > 4096:
        raise web.HTTPUnauthorized(text="Telegram login required")
    if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False)) > 4096:
        raise web.HTTPBadRequest(text="Invalid calculation")
    try:
        auth = safe_parse_webapp_init_data(BOT_TOKEN, init_data)
    except (ValueError, TypeError):
        raise web.HTTPUnauthorized(text="Invalid Telegram login") from None
    auth_time = auth.auth_date
    if auth_time.tzinfo is None:
        auth_time = auth_time.replace(tzinfo=timezone.utc)
    age = time.time() - auth_time.timestamp()
    if auth.user is None or age < -300 or age > 86400:
        raise web.HTTPUnauthorized(text="Expired Telegram login")

    bot = request.app[BOT_APP_KEY]
    bot_replied = False
    report_sent = False

    async def answer(text: str, **kwargs):
        nonlocal bot_replied, report_sent
        await bot.send_message(chat_id=auth.user.id, text=text, **kwargs)
        bot_replied = True
        report_sent = kwargs.get("reply_markup") is not None

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=auth.user.id),
        web_app_data=SimpleNamespace(data=json.dumps(payload, ensure_ascii=False)),
        answer=answer,
    )
    state = SimpleNamespace(clear=lambda: asyncio.sleep(0))
    try:
        await handle_webapp_data(message, state)
    except Exception:
        logger.exception("Mini App analysis delivery failed")
        if not bot_replied:
            try:
                lang = payload.get("lang") if payload.get("lang") in {"ru", "kz", "en"} else "ru"
                await answer(t(lang, "err_internal"))
            except Exception:
                raise web.HTTPBadGateway(text="Could not deliver Telegram report") from None
    return web.json_response({"ok": report_sent, "bot_replied": bot_replied},
                             status=200 if bot_replied else 422)


async def health_check(request: web.Request) -> web.Response:
    """Render and UptimeRobot readiness endpoint; verifies database connectivity."""
    db_health = check_db_health()
    is_healthy = db_health.get("status") in {"connected", "ok"}
    status_code = 200 if is_healthy else 503
    return web.json_response(
        {
            "status": "ok" if is_healthy else "degraded",
            "service": "su-tech-bot",
            "updates": "webhook" if USE_WEBHOOK else "polling",
            "database": db_health,
            "calculation_version": CALCULATION_VERSION,
            "revision": os.getenv("RENDER_GIT_COMMIT", "local")[:12],
        },
        status=status_code,
    )


async def handle_bot_error(event: ErrorEvent) -> bool:
    """Give a user-visible answer when an update handler fails unexpectedly."""
    logger.error("Bot update failed: %s", type(event.exception).__name__)
    update = event.update
    message = update.message
    callback = update.callback_query
    user = message.from_user if message else callback.from_user if callback else None
    lang = get_lang(user.id) if user else "ru"
    text = t(lang, "err_internal")
    try:
        if message:
            await message.answer(text)
        elif callback:
            try:
                await callback.answer(text, show_alert=True)
            except Exception:
                if callback.message:
                    await callback.message.answer(text)
    except Exception:
        logger.exception("Could not send bot error response")
    return True


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.errors.register(handle_bot_error)
    dp.include_router(fields_router)
    dp.include_router(start_router)
    dp.include_router(webapp_router)
    return dp


async def start_http_server(bot: Bot, dp: Dispatcher) -> web.AppRunner:
    """Open the health and Telegram webhook routes before external API calls."""
    app = web.Application(middlewares=[webapp_cors])
    app[BOT_APP_KEY] = bot
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_route("OPTIONS", "/api/analyze", analyze_webapp)
    app.router.add_post("/api/analyze", analyze_webapp)

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
        monitor_task = asyncio.create_task(run_daily_monitor(bot), name="daily-field-monitor")

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
        if 'monitor_task' in locals():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        await runner.cleanup()
        logger.info("Su-Tech bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
