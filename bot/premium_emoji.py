"""Premium Telegram custom emoji selected from the project's emoji catalog.

Every helper keeps the catalog's fallback emoji inside ``tg-emoji`` so Telegram
can display the same message to non-Premium users and system notifications.
"""

PREMIUM_EMOJI: dict[str, tuple[str, str]] = {
    "stats": ("5231200819986047254", "📊"),
    "location": ("5391032818111363540", "📍"),
    "chart_up": ("5449683594425410231", "📈"),
    "checkmark": ("5206607081334906820", "✅"),
    "info": ("5323442290708985472", "ℹ️"),
    "warning": ("5447644880824181073", "⚠️"),
    "cross": ("5210952531676504517", "❌"),
    "calendar": ("5413879192267805083", "📅"),
    "refresh": ("5375338737028841420", "🔄"),
    "settings": ("5341715473882955310", "⚙️"),
    "idea": ("5422439311196834318", "💡"),
    "pin": ("5397782960512444700", "📌"),
}


def pemoji(key: str) -> str:
    """Return a Telegram HTML custom-emoji entity with a safe fallback."""
    try:
        emoji_id, fallback = PREMIUM_EMOJI[key]
    except KeyError as exc:
        raise KeyError(f"Unknown premium emoji key: {key}") from exc
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
