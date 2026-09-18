from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

try:
    from config import WEBAPP_URL
    from i18n import t
except ImportError:
    from bot.config import WEBAPP_URL
    from bot.i18n import t


def get_lang_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-клавиатуру выбора языка.
    Callback-данные: 'lang:kz' и 'lang:ru'.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def get_launch_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Native inline launcher for /app, help and empty-history responses."""
    url_with_lang = f"{WEBAPP_URL}{'&' if '?' in WEBAPP_URL else '?'}lang={lang}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_webapp"),
                    web_app=WebAppInfo(url=url_with_lang),
                )
            ]
        ]
    )


def get_report_inline_keyboard(lang: str = "ru", report_id: str | None = None) -> InlineKeyboardMarkup:
    """
    Возвращает инлайн-кнопки под итоговым агро-отчетом:
      [ 💡 Почему так? / Неліктен осылай? ] (объяснение сохранённого расчёта)
      [ 🔄 Новый расчет / Қайта есептеу ] (WebApp)
      [ 📜 О методике / Толық әдістеме ] (описание FAO-56)
    """
    url_with_lang = f"{WEBAPP_URL}{'&' if '?' in WEBAPP_URL else '?'}lang={lang}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_explain"),
                                  callback_data=f"explain:{report_id or 'unavailable'}")],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_recalculate"),
                    web_app=WebAppInfo(url=url_with_lang),
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_history"),
                    callback_data="show_history_inline",
                ),
                InlineKeyboardButton(
                    text=t(lang, "btn_methodology"),
                    callback_data="methodology:info",
                ),
            ]
        ]
    )


def get_history_carousel_keyboard(lang: str, current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Инлайн-кнопки пагинации карусели истории:
      Ряд 1: [ ⬅️ ] [ Бет X из Y / Стр. X из Y ] [ ➡️ ]
      Ряд 2: [ 🔙 Басты мәзірге / В главное меню ]
    current_page: 0-based index (0 to total_pages - 1)
    """
    page_display = current_page + 1
    page_text = t(lang, "history_page_btn", page=page_display, total=total_pages)

    if total_pages <= 1:
        prev_page = 0
        next_page = 0
    else:
        prev_page = (current_page - 1) % total_pages
        next_page = (current_page + 1) % total_pages

    back_btn_text = t(lang, "history_btn_menu")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️", callback_data=f"hist_page:{prev_page}"),
                InlineKeyboardButton(text=page_text, callback_data=f"hist_page:{current_page}"),
                InlineKeyboardButton(text="➡️", callback_data=f"hist_page:{next_page}"),
            ],
            [
                InlineKeyboardButton(text=back_btn_text, callback_data="hist_menu"),
            ],
        ]
    )
