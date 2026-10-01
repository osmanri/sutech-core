"""Manual release probe on Render; consumes at most three API requests.

Run once with production environment, never from a public HTTP endpoint.
Prints only model IDs/statuses, never credentials, prompts, photos or answers.
All probe history is removed; usage remains counted against the real API quota.
"""

import asyncio
import json
from contextlib import closing
from pathlib import Path
import struct
import sys
import uuid
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_DEEP_MODEL
from bot import db
from bot.services.ai_history import SQLAIHistory
from bot.services.agronomist import AgronomistService, GeminiClient, AIError


def leaf_diagram():
    """Small synthetic PNG for transport verification, not a disease dataset."""
    def chunk(kind, content):
        return (struct.pack(">I", len(content)) + kind + content
                + struct.pack(">I", zlib.crc32(kind + content) & 0xffffffff))
    rows = []
    for y in range(64):
        row = bytearray([0])
        for x in range(64):
            leaf = ((x - 32) / 17) ** 2 + ((y - 30) / 24) ** 2 < 1
            row.extend((35, 130, 60) if leaf else (250, 250, 250))
        rows.append(bytes(row))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


async def check():
    if not GEMINI_API_KEY:
        raise AIError("not_configured")
    db.init_db()
    store = SQLAIHistory()
    # Telegram private user IDs are positive; no real farmer's data is touched.
    user_id = -(uuid.uuid4().int % (2**62) + 1)
    service = AgronomistService(GeminiClient(GEMINI_API_KEY, GEMINI_MODEL),
        deep_client=GeminiClient(GEMINI_API_KEY, GEMINI_DEEP_MODEL, "HIGH"),
        store=store, cooldown=0)
    try:
        result = await service.reply(user_id,
            "Это схематичный рисунок листа. Как безопасно проверить, хватает ли растению воды? Ответь кратко.",
            "ru", leaf_diagram())
        if not result.strip() or result.model != GEMINI_MODEL:
            raise AIError("no_answer")
        print("AI_RELEASE_LITE_PHOTO_OK", result.model, flush=True)
        # A new service represents a restart; the follow-up loads SQL context.
        restarted = AgronomistService(GeminiClient(GEMINI_API_KEY, GEMINI_MODEL),
            deep_client=GeminiClient(GEMINI_API_KEY, GEMINI_DEEP_MODEL, "HIGH"),
            store=store, cooldown=0)
        try:
            result = await restarted.reply(user_id, "А как отличить перелив от нехватки воды?",
                                           "ru", deep=True, allow_fallback=False)
        except AIError:
            print("AI_RELEASE_DEEP_STATUS", json.dumps(restarted.deep_client.last_diagnostic,
                                                        sort_keys=True), flush=True)
            raise
        if not result.strip():
            raise AIError("no_answer")
        print("AI_RELEASE_DEEP_OK" if result.model == GEMINI_DEEP_MODEL else "AI_RELEASE_DEEP_FALLBACK",
              result.model, flush=True)
        print("AI_RELEASE_DEEP_STATUS", json.dumps(restarted.deep_client.last_diagnostic,
                                                    sort_keys=True), flush=True)
        if result.model != GEMINI_DEEP_MODEL or result.fallback:
            raise AIError("deep_fallback")
        if store.page(user_id)["total"] != 2:
            raise AIError("storage_error")
        print("AI_RELEASE_HISTORY_RESTART_OK", "postgresql" if db.is_postgres() else "sqlite", flush=True)
    finally:
        store.reset(user_id, delete=True)
        with closing(db.get_connection()) as conn, conn:
            db.execute_query(conn, "DELETE FROM ai_conversations WHERE user_id = ?", (user_id,))


if __name__ == "__main__":
    try:
        asyncio.run(check())
    except Exception as exc:
        print("AI_RELEASE_CHECK_FAILED", getattr(exc, "code", type(exc).__name__), flush=True)
        sys.exit(1)
