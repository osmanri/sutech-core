"""
user_state.py — In-memory хранилище состояния пользователей Su-Tech.

Хранит:
  1. Выбранный язык интерфейса по user_id ("ru" или "kz").
  2. Историю последних расчетов (до 5 записей на пользователя).
"""

from collections import defaultdict

try:
    from db import get_user_language, set_user_language
except ImportError:
    from bot.db import get_user_language, set_user_language

# {user_id: "ru" | "kz"}
user_langs: dict[int, str] = {}

# {user_id: [record1, record2, ...]}
user_history: dict[int, list[dict]] = defaultdict(list)

_DEFAULT_LANG = "ru"


def get_lang(user_id: int) -> str:
    """Возвращает язык пользователя. Дефолт — 'ru'."""
    if user_id in user_langs:
        return user_langs[user_id]
    persisted = get_user_language(user_id)
    if persisted:
        user_langs[user_id] = persisted
        return persisted
    return _DEFAULT_LANG


def set_lang(user_id: int, lang: str) -> None:
    """Сохраняет выбранный язык пользователя."""
    if lang not in {"ru", "kz"}:
        raise ValueError(f"Unsupported language: {lang}")
    user_langs[user_id] = lang
    set_user_language(user_id, lang)


def add_history(user_id: int, record: dict) -> None:
    """Добавляет запись расчета в историю пользователя (хранит последние 5)."""
    user_history[user_id].insert(0, record)
    user_history[user_id] = user_history[user_id][:5]


def get_history(user_id: int) -> list[dict]:
    """Возвращает список последних расчетов пользователя."""
    return user_history.get(user_id, [])


def clear_all() -> None:
    """Очищает историю и языковые настройки (для тестов)."""
    user_langs.clear()
    user_history.clear()
