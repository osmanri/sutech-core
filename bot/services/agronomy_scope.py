"""Local topic gate: no network calls and no provider quota consumption.

This is a conservative relevance filter, not a semantic classifier. Images need
one multimodal assessment; the system instruction rejects non-plant images.
"""

import re
import unicodedata


DOMAIN_ROOTS = (
    "полив", "орош", "растен", "почв", "грунт", "влаж", "лист", "листь",
    "корен", "корн", "стеб", "семен", "рассад", "урожа", "ферм", "агро",
    "теплиц", "парник", "культур", "пшен", "томат", "помид", "картоф",
    "кукуруз", "хлоп", "рис", "дын", "арбуз", "люцерн", "огур", "перец",
    "капуст", "лук", "сад", "цвет", "сохн", "увяд", "желт", "пятн", "плесен",
    "гнил", "болезн", "вредител", "тл", "клещ", "гриб", "фитофтор", "хлороз",
    "удобр", "азот", "фосфор", "кали", "пестиц", "фунгиц", "гербиц", "мульч",
    "дренаж", "засух", "вод", "дожд", "осад", "испар", "суглин", "песок",
    "глин", "насос", "помп", "расходомер", "датчик", "контроллер", "капель",
    "борозд", "калибров", "агроном", "миллилит", "гектар", "перелив", "недолив",
    "погод", "обработ", "поле", "поля",
    "өсімдік", "суар", "ылғал", "топырақ", "жапырақ", "тамыр", "егін",
    "дақыл", "бидай", "қызанақ", "картоп", "жүгері", "мақта", "күріш",
    "тыңайт", "зиянкес", "ауру", "жылыжай", "қуаң", "сорғы", "тұқым",
    "irrigat", "water", "plant", "crop", "soil", "leaf", "leav", "root",
    "stem", "seed", "harvest", "farm", "agron", "greenhouse", "tomato",
    "wheat", "cotton", "corn", "maize", "potato", "melon", "alfalfa",
    "cucumber", "pepper", "cabbage", "onion", "garden", "pest", "disease",
    "fung", "aphid", "mite", "blight", "chlorosis", "fertiliz", "fertilis",
    "nitrogen", "phosph", "potassium", "nutrient", "moisture", "drought",
    "yellow", "wilt", "rot", "mold", "mould", "loam", "clay", "sand",
    "rain", "evap", "drip", "furrow", "pump", "sensor", "flowmeter",
    "arduino", "esp32", "r385", "yf", "fao", "et0", "etc", "taw", "raw",
    "sutech", "su-tech", "сутех",
)

OFF_TOPIC = re.compile(
    r"\b(?:столиц\w*|президент\w*|политик\w*|биткоин\w*|криптовалют\w*|"
    r"футбол\w*|фильм\w*|анекдот\w*|гороскоп\w*|сочинени\w*|стих\w*|"
    r"capital|president|politics|bitcoin|crypto|football|movie\w*|joke\w*|"
    r"horoscope\w*|poem\w*|essay\w*|астана|фильм|саясат)\b|"
    r"(?:игнорируй|забудь|ignore|forget).{0,35}(?:инструкц|правил|роль|instructions|rules|role)",
    re.IGNORECASE,
)

FOLLOWUP = re.compile(
    r"^(?:а\s+|и\s+|and\s+|but\s+)?(?:как|что|чем|почему|сколько|когда|где|"
    r"какие|какой|можно|нужно|надо|объясни|поясни|подробнее|продолжи|"
    r"провер|обработ|помог|это|они|он|она|да|нет|не|два|три|"
    r"how|what|why|when|where|which|can|should|explain|more|continue|"
    r"yes|no|it|they|check|two|three|"
    r"қалай|неге|қашан|қанша|қай|не|түсіндір|иә|жоқ)\b|^\d",
    re.IGNORECASE,
)


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")


def has_domain(text: str) -> bool:
    words = re.findall(r"[\w-]+", normalized(text))
    return (bool(re.search(r"\bsu[\s-]+tech\b|\bсу[\s-]+тех\b", normalized(text)))
            or any(word.startswith(root) for word in words for root in DOMAIN_ROOTS))


def in_scope(text: str, history: list[dict], *, has_image: bool = False) -> bool:
    text = normalized(text).strip()
    if OFF_TOPIC.search(text):
        return False
    if has_image or has_domain(text):
        return True
    # Only this user's bounded conversation can license a contextual follow-up.
    # Never use model thoughts or a different user's conversation as evidence.
    if not history or len(text) > 180 or not FOLLOWUP.search(text):
        return False
    observations = " ".join(part.get("text", "") for turn in history
                            if turn.get("role") == "user"
                            for part in turn.get("parts", [])
                            if isinstance(part.get("text"), str))
    return has_domain(observations) or "[new plant photo" in observations.casefold()
