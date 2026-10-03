"""Private-chat UI message IDs. Calculation and AI history are stored separately."""
import time
from contextlib import closing
from bot import db

MAX_MESSAGES = 200


def init_chat_screen_table(conn):
    db.execute_query(conn, '''CREATE TABLE IF NOT EXISTS chat_ui_messages (
        chat_id BIGINT NOT NULL CHECK (chat_id > 0),
        message_id BIGINT NOT NULL CHECK (message_id > 0),
        kind TEXT NOT NULL CHECK (kind IN ('bot','user')),
        created_at BIGINT NOT NULL CHECK (created_at > 0),
        PRIMARY KEY (chat_id,message_id)
    )''')
    db.execute_query(conn, 'CREATE INDEX IF NOT EXISTS idx_chat_ui_messages_age ON chat_ui_messages(created_at)')
    # Old Telegram messages cannot be deleted; keep IDs long enough to disable
    # stale inline buttons, without accumulating an unbounded message registry.
    db.execute_query(conn, 'DELETE FROM chat_ui_messages WHERE created_at < ?',
                     (int(time.time()) - 7 * 86400,))
    conn.commit()


def remember(chat_id, message_id, kind, created_at):
    if chat_id <= 0 or message_id <= 0 or kind not in ('bot', 'user'):
        raise ValueError('Invalid private-chat message')
    with closing(db.get_connection()) as conn, conn:
        db.execute_query(conn, '''INSERT INTO chat_ui_messages
            (chat_id,message_id,kind,created_at) VALUES (?,?,?,?)
            ON CONFLICT(chat_id,message_id) DO NOTHING''',
                         (chat_id,message_id,kind,created_at))
        db.execute_query(conn, '''DELETE FROM chat_ui_messages
            WHERE chat_id=? AND message_id NOT IN (
                SELECT message_id FROM chat_ui_messages WHERE chat_id=?
                ORDER BY created_at DESC,message_id DESC LIMIT ?
            )''', (chat_id,chat_id,MAX_MESSAGES))


def messages(chat_id):
    with closing(db.get_connection()) as conn:
        rows = db.execute_query(conn, '''SELECT message_id,kind,created_at
            FROM chat_ui_messages WHERE chat_id=? ORDER BY message_id''',
                                (chat_id,)).fetchall()
    return {int(r[0]): {'kind':r[1], 'created_at':int(r[2])} for r in rows}


def forget(chat_id, message_ids):
    ids = [int(i) for i in message_ids if int(i) > 0]
    if not ids:
        return
    with closing(db.get_connection()) as conn, conn:
        placeholders = ','.join('?' for _ in ids)
        db.execute_query(conn,
            f'DELETE FROM chat_ui_messages WHERE chat_id=? AND message_id IN ({placeholders})',
            (chat_id,*ids))
