"""Database-backed AI behavior: restart, ownership, reset races and quotas."""

import asyncio
import base64
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from bot import db
from bot.services.ai_history import SQLAIHistory, HistoryError, init_ai_tables, MAX_EXCHANGES
from bot.services.agronomist import AgronomistService, GeminiReply, AIError

JPEG = b"\xff\xd8\xfftest"


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path_patch = patch.object(db, "DB_PATH", str(Path(self.temp.name) / "ai.db"))
        self.engine_patch = patch.object(db, "is_postgres", return_value=False)
        self.path_patch.start()
        self.engine_patch.start()
        with closing(db.get_connection()) as conn:
            init_ai_tables(conn)
            init_ai_tables(conn)  # Restart migration is idempotent.
        self.store = SQLAIHistory()
        self.lite = SimpleNamespace(configured=True, model="gemini-3.5-flash-lite",
                                    generate=AsyncMock(return_value="Ответ о растении"))
        self.deep = SimpleNamespace(configured=True, model="gemini-3.8-flash",
                                    generate=AsyncMock(return_value="Подробный ответ"))

    async def asyncTearDown(self):
        self.engine_patch.stop()
        self.path_patch.stop()
        self.temp.cleanup()

    def service(self, **kwargs):
        return AgronomistService(self.lite, cooldown=0, store=self.store,
                                 deep_client=self.deep, **kwargs)

    async def test_restart_restores_signed_context_but_never_image_bytes(self):
        signed = [{"text": "Private thought", "thought": True, "thoughtSignature": "signed"},
                  {"text": "Проверьте нижнюю сторону листа"}]
        self.lite.generate.return_value = GeminiReply("Проверьте нижнюю сторону листа", signed)
        first = self.service()
        await first.reply(1, "Пшеница", "ru", JPEG)
        second = self.service()
        self.assertTrue(await second.is_active(1))
        await second.reply(1, "Что там искать?", "ru")
        self.assertEqual(self.lite.generate.await_args.args[0][1]["parts"], signed)
        page = await second.history_page(1)
        self.assertEqual(page["total"], 2)
        self.assertNotIn("Private thought", page["entry"]["answer"])
        with closing(db.get_connection()) as conn:
            raw = conn.execute("SELECT context_json FROM ai_conversations WHERE user_id=1").fetchone()[0]
        self.assertNotIn("inlineData", raw)
        self.assertNotIn(base64.b64encode(JPEG).decode(), raw)

    async def test_exit_and_reentry_keep_history_and_context(self):
        service = self.service()
        await service.reply(1, "Культура: томат", "ru")
        await service.set_active(1, False)
        self.assertFalse(await self.service().is_active(1))
        await service.set_active(1, True)
        await self.service().reply(1, "Как поливать?", "ru")
        self.assertIn("томат", str(self.lite.generate.await_args.args[0]))
        self.assertEqual(self.store.page(1)["total"], 2)

    async def test_new_dialog_retains_archive_delete_is_owner_scoped(self):
        service = self.service()
        await service.reply(1, "User one's private crop question", "en")
        await service.reply(2, "Other user's crop question", "en")
        await service.reset(1)
        self.assertEqual(self.store.load(1)["history"], [])
        self.assertEqual(self.store.page(1)["total"], 1)
        self.assertEqual(self.store.page(999)["total"], 0)
        await service.reset(1, delete=True)
        self.assertEqual(self.store.page(1)["total"], 0)
        self.assertEqual(self.store.page(2)["total"], 1)
        self.assertTrue(self.store.load(2)["history"])

    async def test_deep_uses_distinct_model_and_strips_foreign_signatures(self):
        self.lite.generate.return_value = GeminiReply("Visible answer", [
            {"text": "Hidden", "thought": True, "thoughtSignature": "lite-signature"},
            {"text": "Visible answer", "thoughtSignature": "another-lite-signature"}])
        service = self.service()
        await service.reply(1, "Irrigation question", "en")
        answer = await service.reply(1, "Analyze irrigation in depth", "en", deep=True)
        self.assertEqual(answer.model, self.deep.model)
        history = self.deep.generate.await_args.args[0]
        self.assertIn("Visible answer", str(history))
        self.assertNotIn("thoughtSignature", str(history))
        self.assertNotIn("Hidden", str(history))

    async def test_deep_provider_failure_falls_back_and_records_actual_model(self):
        self.deep.generate.side_effect = AIError("quota")
        answer = await self.service().reply(1, "Leaf spots", "en", JPEG, deep=True)
        self.assertTrue(answer.fallback)
        self.assertEqual(answer.model, self.lite.model)
        self.assertEqual(self.lite.generate.await_args.args[3], JPEG)
        self.assertEqual(self.store.page(1)["entry"]["model"], self.lite.model)

    async def test_deep_retry_charges_each_attempt_and_strict_probe_never_uses_lite(self):
        self.deep.generate.side_effect = [AIError("unavailable", retryable=True), "Ответ 3.8"]
        with patch("bot.services.agronomist.asyncio.sleep", new_callable=AsyncMock):
            answer = await self.service().reply(1, "Irrigation question", "en", deep=True, allow_fallback=False)
        self.assertEqual(answer.model, self.deep.model)
        self.assertFalse(answer.fallback)
        with closing(db.get_connection()) as conn:
            attempts = conn.execute("SELECT COUNT(*) FROM ai_usage WHERE user_id=1").fetchone()[0]
        self.assertEqual(attempts, 2)
        self.assertEqual(self.store.page(1)["total"], 1)
        self.lite.generate.assert_not_called()
        self.deep.generate.side_effect = AIError("quota")
        with self.assertRaises(AIError) as error:
            await self.service().reply(2, "Irrigation question", "en", deep=True, allow_fallback=False)
        self.assertEqual(error.exception.code, "quota")
        self.lite.generate.assert_not_called()

    async def test_deep_retry_stops_when_user_quota_is_exhausted(self):
        self.deep.generate.side_effect = AIError("unavailable", retryable=True)
        with patch("bot.services.agronomist.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(AIError) as error:
                await self.service(user_daily_limit=1).reply(1, "Irrigation question", "en", deep=True)
        self.assertEqual(error.exception.code, "daily_limit")
        self.deep.generate.assert_awaited_once()
        self.lite.generate.assert_not_called()

    async def test_full_deep_quota_falls_back_without_spending_provider_request(self):
        for _ in range(18):
            self.store.reserve(2, self.deep.model, 18, 100, 100, 0)
        answer = await self.service().reply(1, "Irrigation question", "en", deep=True)
        self.assertTrue(answer.fallback)
        self.deep.generate.assert_not_called()
        self.lite.generate.assert_awaited_once()

    async def test_reset_from_another_worker_cancels_late_answer(self):
        ready, release = asyncio.Event(), asyncio.Event()

        async def slow(*args):
            ready.set()
            await release.wait()
            return "Stale answer"

        self.lite.generate.side_effect = slow
        task = asyncio.create_task(self.service().reply(1, "Irrigation question", "en"))
        await ready.wait()
        await self.service().reset(1, delete=True)
        release.set()
        with self.assertRaises(AIError) as error:
            await task
        self.assertEqual(error.exception.code, "cancelled")
        self.assertEqual(self.store.page(1)["total"], 0)
        self.assertEqual(self.store.load(1)["history"], [])

    async def test_quota_survives_restart_history_deletion_and_explicit_model_change(self):
        await self.service(user_daily_limit=1).reply(1, "Irrigation question", "en")
        await self.service().reset(1, delete=True)
        with self.assertRaises(AIError) as error:
            await self.service(user_daily_limit=1).reply(1, "Another irrigation question", "en", deep=True)
        self.assertEqual(error.exception.code, "daily_limit")
        self.deep.generate.assert_not_called()

    def test_parallel_workers_cannot_over_reserve_global_quota(self):
        def attempt(uid):
            try:
                SQLAIHistory().reserve(uid, "lite", 2, 100, 100, 0)
                return True
            except HistoryError:
                return False
        with ThreadPoolExecutor(max_workers=6) as pool:
            self.assertEqual(sum(pool.map(attempt, range(12))), 2)

    def test_quota_minute_and_cooldown_are_independent_of_daily_quota(self):
        self.store.reserve(1, "lite", 500, 100, 1, 3)
        with self.assertRaises(HistoryError) as error:
            self.store.reserve(2, "lite", 500, 100, 1, 3)
        self.assertEqual(error.exception.code, "rate_limit")
        with self.assertRaises(HistoryError) as error:
            self.store.reserve(1, "deep", 20, 100, 5, 3)
        self.assertEqual(error.exception.code, "cooldown")

    def test_archive_bound_and_pagination_retain_latest_full_answers(self):
        for index in range(MAX_EXCHANGES + 3):
            saved = self.store.load(1)
            with patch("bot.services.ai_history.time.time_ns", return_value=(index + 1) * 1_000_000):
                self.store.save(1, saved["version"], [], str(index), "Answer" * 500, "lite", False)
        page = self.store.page(1)
        self.assertEqual(page["total"], MAX_EXCHANGES)
        self.assertEqual(page["entry"]["question"], str(MAX_EXCHANGES + 2))
        self.assertEqual(page["entry"]["answer"], "Answer" * 500)
        self.assertEqual(self.store.page(1, 999)["entry"]["question"], "3")

    async def test_storage_failure_never_sends_unsaved_request(self):
        with patch.object(self.store, "load", side_effect=RuntimeError("secret database URL")):
            with self.assertRaises(AIError) as error:
                await self.service().reply(1, "Irrigation question", "en")
        self.assertEqual(error.exception.code, "storage_error")
        self.assertNotIn("secret", str(error.exception))
        self.lite.generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
