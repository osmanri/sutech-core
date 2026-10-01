"""Private, bounded AI history and restart-safe quotas on the existing database.

No photos or Telegram file IDs are stored. Every history query is owner-scoped.
The provider request runs outside database transactions.
"""

from contextlib import closing
import json
import time
import uuid

from bot import db

MAX_EXCHANGES = 100


class HistoryError(Exception):
    """Safe error code; never expose database URLs or query parameters."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def init_ai_tables(conn):
    for statement in (
        """CREATE TABLE IF NOT EXISTS ai_conversations (
            user_id BIGINT PRIMARY KEY,
            context_json TEXT NOT NULL DEFAULT '[]',
            model TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1))
        )""",
        """CREATE TABLE IF NOT EXISTS ai_exchanges (
            id TEXT PRIMARY KEY, user_id BIGINT NOT NULL,
            created_at BIGINT NOT NULL, question TEXT NOT NULL,
            answer TEXT NOT NULL, model TEXT NOT NULL,
            has_image INTEGER NOT NULL CHECK (has_image IN (0, 1))
        )""",
        """CREATE INDEX IF NOT EXISTS idx_ai_exchanges_owner
            ON ai_exchanges (user_id, created_at DESC, id DESC)""",
        """CREATE TABLE IF NOT EXISTS ai_usage (
            id TEXT PRIMARY KEY, user_id BIGINT NOT NULL,
            model TEXT NOT NULL, created_at BIGINT NOT NULL
        )""",
        """CREATE INDEX IF NOT EXISTS idx_ai_usage_model_time
            ON ai_usage (model, created_at)""",
        """CREATE INDEX IF NOT EXISTS idx_ai_usage_owner_time
            ON ai_usage (user_id, created_at)""",
    ):
        db.execute_query(conn, statement)
    ensure = db._ensure_columns_postgres if db.is_postgres() else db._ensure_columns_sqlite
    ensure(conn.cursor(), "ai_conversations", {"active": "INTEGER NOT NULL DEFAULT 0"})
    conn.commit()


def _ensure_conversation(conn, user_id):
    db.execute_query(conn, """INSERT INTO ai_conversations (user_id) VALUES (?)
        ON CONFLICT (user_id) DO NOTHING""", (user_id,))


class SQLAIHistory:
    def load(self, user_id):
        with closing(db.get_connection()) as conn, conn:
            _ensure_conversation(conn, user_id)
            row = db.execute_query(conn, """SELECT context_json, model, version, active
                FROM ai_conversations WHERE user_id = ?""", (user_id,)).fetchone()
            return {"history": json.loads(row[0]), "model": row[1], "version": row[2], "active": bool(row[3])}

    def set_active(self, user_id, active):
        with closing(db.get_connection()) as conn, conn:
            _ensure_conversation(conn, user_id)
            db.execute_query(conn, """UPDATE ai_conversations SET active = ?,
                version = version + 1 WHERE user_id = ?""", (int(active), user_id))

    def reset(self, user_id, delete=False):
        with closing(db.get_connection()) as conn, conn:
            _ensure_conversation(conn, user_id)
            db.execute_query(conn, """UPDATE ai_conversations SET context_json = '[]',
                model = '', active = 1, version = version + 1 WHERE user_id = ?""", (user_id,))
            if delete:
                db.execute_query(conn, "DELETE FROM ai_exchanges WHERE user_id = ?", (user_id,))
            # Usage deliberately survives a conversation reset or history deletion.

    def save(self, user_id, version, history, question, answer, model, has_image):
        with closing(db.get_connection()) as conn, conn:
            updated = db.execute_query(conn, """UPDATE ai_conversations
                SET context_json = ?, model = ?, active = 1, version = version + 1
                WHERE user_id = ? AND version = ?""",
                (json.dumps(history, ensure_ascii=False), model, user_id, version))
            if updated.rowcount != 1:
                raise HistoryError("cancelled")
            db.execute_query(conn, """INSERT INTO ai_exchanges
                (id, user_id, created_at, question, answer, model, has_image)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (uuid.uuid4().hex, user_id, time.time_ns() // 1_000_000,
                 question, str(answer), model, int(has_image)))
            db.execute_query(conn, """DELETE FROM ai_exchanges WHERE user_id = ? AND id NOT IN
                (SELECT id FROM ai_exchanges WHERE user_id = ?
                 ORDER BY created_at DESC, id DESC LIMIT ?)""", (user_id, user_id, MAX_EXCHANGES))

    def page(self, user_id, offset=0):
        offset = min(max(int(offset), 0), MAX_EXCHANGES - 1)
        with closing(db.get_connection()) as conn, conn:
            total = db.execute_query(conn, "SELECT COUNT(*) FROM ai_exchanges WHERE user_id = ?",
                                     (user_id,)).fetchone()[0]
            offset = min(offset, max(total - 1, 0))
            row = db.execute_query(conn, """SELECT created_at, question, answer, model, has_image
                FROM ai_exchanges WHERE user_id = ? ORDER BY created_at DESC, id DESC
                LIMIT 1 OFFSET ?""", (user_id, offset)).fetchone()
            return {"total": total, "offset": offset, "entry": dict(row) if row else None}

    def reserve(self, user_id, model, daily_limit, user_daily_limit, rpm, cooldown):
        """Serialize only the short quota check, across workers and restarts."""
        now = int(time.time() * 1000)
        with closing(db.get_connection()) as conn, conn:
            if db.is_postgres():
                db.execute_query(conn, "SELECT pg_advisory_xact_lock(?)", (742816031,))
            else:
                db.begin_immediate(conn)
            db.execute_query(conn, "DELETE FROM ai_usage WHERE created_at < ?", (now - 86_400_000,))
            own = db.execute_query(conn, """SELECT COUNT(*), MAX(created_at)
                FROM ai_usage WHERE user_id = ?""", (user_id,)).fetchone()
            model_count = db.execute_query(conn, """SELECT COUNT(*) FROM ai_usage
                WHERE model = ?""", (model,)).fetchone()[0]
            minute_count = db.execute_query(conn, """SELECT COUNT(*) FROM ai_usage
                WHERE model = ? AND created_at > ?""", (model, now - 60_000)).fetchone()[0]
            if own[0] >= user_daily_limit or model_count >= daily_limit:
                raise HistoryError("daily_limit")
            if minute_count >= rpm:
                raise HistoryError("rate_limit")
            if own[1] is not None and now - own[1] < cooldown * 1000:
                raise HistoryError("cooldown")
            db.execute_query(conn, """INSERT INTO ai_usage (id, user_id, model, created_at)
                VALUES (?, ?, ?, ?)""", (uuid.uuid4().hex, user_id, model, now))
