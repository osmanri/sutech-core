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


def get_report_inline_keyboard(lang: str = "ru", report_id: str | None = None,
                               field_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Возвращает компактные инлайн-кнопки под итоговым агро-отчетом (3 ряда):
      Ряд 1: [ 💡 Почему так? ] + [ 💧 Отметить полив ] (если поле сохранено)
      Ряд 2: [ 🌱 Мои поля ] + [ 🔄 Новый расчет ]
      Ряд 3: [ 📄 Экспорт CSV ] + [ 📊 История ]
    """
    url_with_lang = f"{WEBAPP_URL}{'&' if '?' in WEBAPP_URL else '?'}lang={lang}"
    rows = []
    
    # Ряд 1: Главные действия по отчету
    row1 = [InlineKeyboardButton(text=t(lang, "btn_explain"),
                                 callback_data=f"explain:{report_id or 'unavailable'}")]
    if field_id is not None:
        row1.append(InlineKeyboardButton(text=t(lang, "btn_field_watered"),
                                         callback_data=f"field:watered:{field_id}"))
    rows.append(row1)

    # Ряд 2: Поля и Новый расчет
    row2 = []
    if field_id is not None:
        row2.append(InlineKeyboardButton(text=t(lang, "btn_fields"), callback_data="fields:list"))
    row2.append(InlineKeyboardButton(text=t(lang, "btn_recalculate"),
                                     web_app=WebAppInfo(url=url_with_lang)))
    rows.append(row2)

    # Ряд 3: Экспорт, История
    row3 = []
    if field_id is not None:
        row3.append(InlineKeyboardButton(text=t(lang, "btn_export_field"),
                                         callback_data=f"field:export:{field_id}"))
    row3.append(InlineKeyboardButton(text=t(lang, "btn_history"),
                                     callback_data="show_history_inline"))
    rows.append(row3)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_fields_keyboard(lang: str, fields: list[dict]) -> InlineKeyboardMarkup:
    """One compact row per saved field: refresh balance and record irrigation."""
    rows = []
    for field in fields[:20]:
        crop_key = f"report_crop_{field['crop_type']}"
        crop = t(lang, crop_key)
        rows.append([
            InlineKeyboardButton(
                text=f"{crop} · {float(field.get('area_ha') or 0):g} га",
                callback_data=f"field:update:{field['id']}",
            ),
            InlineKeyboardButton(
                text="💧",
                callback_data=f"field:watered:{field['id']}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_irrigation_confirmation_keyboard(lang: str, field_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_confirm_watered"),
                             callback_data=f"field:confirm-watered:{field_id}"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="field:cancel-watered"),
    ]])


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
