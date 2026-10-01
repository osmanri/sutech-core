from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from bot.ai_i18n import ai_text

try:
    from config import WEBAPP_URL
    from i18n import t
except ImportError:
    from bot.config import WEBAPP_URL
    from bot.i18n import t


def get_main_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """
    Короткое главное меню: только действия, которыми фермер пользуется чаще всего.
    """
    url_with_lang = f"{WEBAPP_URL}{'&' if '?' in WEBAPP_URL else '?'}lang={lang}"

    return ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1 (на всю ширину): WebApp кнопка
            [
                KeyboardButton(
                    text=t(lang, "btn_webapp"),
                    web_app=WebAppInfo(url=url_with_lang),
                )
            ],
            [KeyboardButton(text=ai_text(lang, "button"), style="success")],
            # Основные действия: расчёт, ИИ, поля и история.
            [
                KeyboardButton(text=t(lang, "btn_fields")),
                KeyboardButton(text=t(lang, "btn_history")),
            ],
            [
                KeyboardButton(text=t(lang, "btn_more")),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def get_more_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """Secondary menu for infrequent actions; keeps the daily menu uncluttered."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_lang")),
             KeyboardButton(text=t(lang, "btn_help"))],
            [KeyboardButton(text=t(lang, "btn_about"))],
            [KeyboardButton(text=t(lang, "btn_back"))],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# Псевдонимы для 100% обратной совместимости
get_webapp_keyboard = get_main_reply_keyboard
get_main_keyboard = get_main_reply_keyboard
