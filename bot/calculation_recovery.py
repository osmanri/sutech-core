"""Owner-scoped retry state and read-only access to a dated previous result."""
import asyncio
from datetime import date
from html import escape

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.balance_report import display_volume
from bot.i18n import t


class CalculationRecovery(StatesGroup):
    ready = State()
    calculating = State()


COPY = {
    'error': ('Не удалось получить погоду. Введённые параметры сохранены. Повторите расчёт — заполнять форму заново не нужно.',
              'Ауа райын алу мүмкін болмады. Енгізілген параметрлер сақталды. Нысанды қайта толтырмай, есепті қайталаңыз.',
              'Weather is unavailable. Your inputs are saved. Retry without filling in the form again.'),
    'retry': ('Повторить расчёт', 'Есепті қайталау', 'Retry calculation'),
    'working': ('Получаю погоду и считаю полив…', 'Ауа райын алып, суаруды есептеймін…', 'Fetching weather and calculating irrigation…'),
    'busy': ('Расчёт уже выполняется…', 'Есеп орындалып жатыр…', 'Calculation is already running…'),
    'expired': ('Откройте новый расчёт: эта кнопка больше не действует.', 'Жаңа есепті ашыңыз: бұл батырма енді жарамсыз.', 'Start a new calculation: this button is no longer active.'),
    'last': ('Последний сохранённый результат', 'Соңғы сақталған нәтиже', 'Last saved result'),
    'old': ('Это результат за указанную дату. Сегодняшняя погода не получена; не используйте этот объём как свежую рекомендацию.',
            'Бұл көрсетілген күннің нәтижесі. Бүгінгі ауа райы алынбады; осы көлемді жаңа ұсыным ретінде қолданбаңыз.',
            'This result is for the date shown. Current weather is unavailable; do not treat this volume as a fresh recommendation.'),
    'empty': ('Сохранённого результата пока нет.', 'Сақталған нәтиже әлі жоқ.', 'No saved result yet.'),
    'cancel': ('Отменить', 'Болдырмау', 'Cancel'),
}
active_calculations = {}


def phrase(lang, key):
    return COPY[key][{'ru': 0, 'kz': 1, 'en': 2}.get(lang, 0)]


def stop_calculation(user_id):
    task = active_calculations.pop(user_id, None)
    if task and not task.done():
        task.cancel()


def retry_is_duplicate(user_id, data):
    task = active_calculations.get(user_id)
    return bool(task and not task.done() and (data or '').startswith('calc:retry:'))


def recovery_keyboard(lang, token, *, loading=False):
    rows = [] if loading else [[InlineKeyboardButton(text=phrase(lang, 'retry'), callback_data=f'calc:retry:{token}')]]
    rows.append([InlineKeyboardButton(text=phrase(lang, 'cancel') if loading else t(lang, 'btn_back'), callback_data='ui:home')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def previous_snapshot(field_id, user_id):
    # Use the existing journal and its ownership check. Never recalculate,
    # change the stored deficit, or apply old weather on a recovery screen.
    from bot.field_state import list_daily_balances
    import json
    rows = await asyncio.to_thread(list_daily_balances, field_id, user_id=user_id, limit=1)
    if not rows:
        return None
    row = rows[0]
    result = json.loads(row['result_json'])
    return {'date': row['balance_date'], 'timezone': row.get('timezone') or '',
            'volume': result['gross_m3']}


def format_previous(lang, snapshot):
    if snapshot is None:
        return phrase(lang, 'empty')
    stamp = date.fromisoformat(snapshot['date']).strftime('%d.%m.%Y')
    return (f"<b>{phrase(lang, 'last')}</b>\n"
            f"{stamp} · {escape(snapshot['timezone'])}\n"
            f"{display_volume(lang, snapshot['volume'])}\n\n{phrase(lang, 'old')}")
