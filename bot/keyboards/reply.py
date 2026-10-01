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
    Основное меню: Mini App, ИИ-агроном, поля, история и справка.
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
            # Ряд 2: История и Язык
            [
                KeyboardButton(text=t(lang, "btn_fields")),
                KeyboardButton(text=t(lang, "btn_history")),
            ],
            # Ряд 3: О системе и Помощь
            [
                KeyboardButton(text=t(lang, "btn_lang")),
                KeyboardButton(text=t(lang, "btn_about")),
                KeyboardButton(text=t(lang, "btn_help")),
            ],
        ],
        resize_keyboard=True,
        persistent=True,
    )


# Псевдонимы для 100% обратной совместимости
get_webapp_keyboard = get_main_reply_keyboard
get_main_keyboard = get_main_reply_keyboard
