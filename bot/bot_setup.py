"""Telegram profile, commands and Mini App menu configuration."""

import logging

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    MenuButtonWebApp,
    WebAppInfo,
)

try:
    from config import WEBAPP_URL
except ImportError:
    from bot.config import WEBAPP_URL

logger = logging.getLogger(__name__)


COMMANDS = {
    "ru": [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="app", description="Открыть расчет полива"),
        BotCommand(command="fields", description="Сохранённые поля"),
        BotCommand(command="history", description="История расчетов"),
        BotCommand(command="language", description="Сменить язык"),
        BotCommand(command="help", description="Как пользоваться"),
        BotCommand(command="about", description="О системе Su-Tech"),
    ],
    "kz": [
        BotCommand(command="start", description="Басты мәзір"),
        BotCommand(command="app", description="Суару есебін ашу"),
        BotCommand(command="fields", description="Сақталған алқаптар"),
        BotCommand(command="history", description="Есептеулер тарихы"),
        BotCommand(command="language", description="Тілді өзгерту"),
        BotCommand(command="help", description="Пайдалану нұсқаулығы"),
        BotCommand(command="about", description="Su-Tech жүйесі туралы"),
    ],
}

PROFILE = {
    "ru": {
        "name": "Su-Tech | Умный полив",
        "short": "Расчет полива поля по FAO-56 и данным Open-Meteo.",
        "description": (
            "Su-Tech рассчитывает суточную норму полива по модели FAO-56. "
            "Отметьте поле на карте, выберите культуру и способ полива — "
            "бот учтет погоду Open-Meteo и пришлет краткий агро-отчет."
        ),
    },
    "kz": {
        "name": "Su-Tech | Ақылды суару",
        "short": "FAO-56 және Open-Meteo бойынша суару есебі.",
        "description": (
            "Su-Tech FAO-56 моделі бойынша тәуліктік суару нормасын есептейді. "
            "Картадан алқапты белгілеңіз, дақыл мен суару әдісін таңдаңыз — "
            "бот Open-Meteo деректерін ескеріп, қысқа агро-есеп жібереді."
        ),
    },
}


def webapp_url(lang: str) -> str:
    """Return a localized Mini App URL without duplicating query separators."""
    separator = "&" if "?" in WEBAPP_URL else "?"
    return f"{WEBAPP_URL}{separator}lang={lang}"


async def configure_user_menu(bot: Bot, chat_id: int, lang: str) -> None:
    """Set a localized native Telegram menu button for one private chat."""
    await bot.set_chat_menu_button(
        chat_id=chat_id,
        menu_button=MenuButtonWebApp(
            text="Su-Tech ашу" if lang == "kz" else "Открыть Su-Tech",
            web_app=WebAppInfo(url=webapp_url(lang)),
        ),
    )


async def configure_bot_profile(bot: Bot) -> None:
    """Configure commands, profile copy and the default Mini App menu button."""
    scope = BotCommandScopeAllPrivateChats()
    operations = [
        ("default commands", lambda: bot.set_my_commands(COMMANDS["ru"], scope=scope)),
        (
            "Russian commands",
            lambda: bot.set_my_commands(COMMANDS["ru"], scope=scope, language_code="ru"),
        ),
        # Telegram uses ISO 639-1 code `kk` for Kazakh; the app itself uses `kz`.
        (
            "Kazakh commands",
            lambda: bot.set_my_commands(COMMANDS["kz"], scope=scope, language_code="kk"),
        ),
        (
            "default menu",
            lambda: bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть Su-Tech",
                    web_app=WebAppInfo(url=webapp_url("ru")),
                )
            ),
        ),
    ]

    for lang, language_code in (("ru", "ru"), ("kz", "kk")):
        profile = PROFILE[lang]
        operations.extend(
            [
                (
                    f"{lang} name",
                    lambda profile=profile, language_code=language_code: bot.set_my_name(
                        name=profile["name"], language_code=language_code
                    ),
                ),
                (
                    f"{lang} short description",
                    lambda profile=profile, language_code=language_code: bot.set_my_short_description(
                        short_description=profile["short"],
                        language_code=language_code,
                    ),
                ),
                (
                    f"{lang} description",
                    lambda profile=profile, language_code=language_code: bot.set_my_description(
                        description=profile["description"],
                        language_code=language_code,
                    ),
                ),
            ]
        )

    for label, operation in operations:
        try:
            await operation()
        except Exception as exc:
            # Optional profile polish must never prevent the bot from receiving
            # updates if Telegram temporarily rejects one localized setting.
            logger.warning("Telegram setup skipped (%s): %s", label, exc)
