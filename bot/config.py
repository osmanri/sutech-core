import os
from dotenv import load_dotenv

# Загружаем .env относительно директории бота или текущей директории
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://su-tech-mvp.vercel.app")

if not BOT_TOKEN:
    raise ValueError(
        "\n❌  Токен бота не найден!\n"
        "📝  Создайте файл bot/.env и добавьте:\n"
        "    BOT_TOKEN=ваш_токен_от_botfather\n"
        "🤖  Получить токен: @BotFather → /newbot\n"
    )
