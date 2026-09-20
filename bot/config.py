import hashlib
import os
from dotenv import load_dotenv

# Загружаем .env относительно директории бота или текущей директории
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://frontend-2-mauve.vercel.app")

# Render exposes its public HTTPS address through RENDER_EXTERNAL_URL. Local
# development stays on polling unless USE_WEBHOOK is explicitly enabled.
IS_RENDER: bool = bool(os.getenv("RENDER_SERVICE_ID")) or os.getenv("RENDER", "").lower() == "true"
PUBLIC_BASE_URL: str = (
    os.getenv("PUBLIC_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or ("https://sutech-core.onrender.com" if IS_RENDER else "")
).rstrip("/")
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/telegram/webhook")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

if not BOT_TOKEN:
    raise ValueError(
        "\n❌  Токен бота не найден!\n"
        "📝  Создайте файл bot/.env и добавьте:\n"
        "    BOT_TOKEN=ваш_токен_от_botfather\n"
        "🤖  Получить токен: @BotFather → /newbot\n"
    )

USE_WEBHOOK: bool = _env_flag("USE_WEBHOOK", IS_RENDER)
WEBHOOK_URL: str = f"{PUBLIC_BASE_URL}{WEBHOOK_PATH}" if PUBLIC_BASE_URL else ""
# Telegram accepts only A-Z, a-z, 0-9, _ and -. A deterministic hash avoids
# requiring another secret on Render while never exposing the bot token.
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET") or hashlib.sha256(
    f"su-tech:{BOT_TOKEN}".encode("utf-8")
).hexdigest()

if USE_WEBHOOK and not WEBHOOK_URL:
    raise ValueError("USE_WEBHOOK включён, но PUBLIC_BASE_URL/RENDER_EXTERNAL_URL не задан")
