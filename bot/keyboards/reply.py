from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

try:
    from config import WEBAPP_URL
    from i18n import t
except ImportError:
    from bot.config import WEBAPP_URL
    from bot.i18n import t


def get_main_reply_keyboard(lang: str = "ru") -> ReplyKeyboardMarkup:
    """
    Возвращает постоянную нижнюю клавиатуру (Reply Menu) Su-Tech:
      - Ряд 1: 🌿 Открыть Su-Tech / 🌿 Su-Tech ашу (WebApp-кнопка на всю ширину)
      - Ряд 2: 📊 История / 📊 Тарих | ⚙️ Язык / ⚙️ Тіл
      - Ряд 3: 📜 О системе / 📜 Жүйе туралы | ❓ Помощь / ❓ Көмек
    """
    url_with_lang = f"{WEBAPP_URL}?lang={lang}"

    return ReplyKeyboardMarkup(
        keyboard=[
            # Ряд 1 (на всю ширину): WebApp кнопка
            [
                KeyboardButton(
                    text=t(lang, "btn_webapp"),
                    web_app=WebAppInfo(url=url_with_lang),
                )
            ],
            # Ряд 2: История и Язык
            [
                KeyboardButton(text=t(lang, "btn_history")),
                KeyboardButton(text=t(lang, "btn_lang")),
            ],
            # Ряд 3: О системе и Помощь
            [
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
