"""Opt-in pilot interest and owner-scoped feedback; no contacts or photos."""
from contextlib import closing
from bot import db


def init_pilot_tables(conn):
    timestamp = 'TIMESTAMPTZ' if db.is_postgres() else 'TEXT'
    for sql in (
        f'''CREATE TABLE IF NOT EXISTS pilot_participants (
            user_id BIGINT PRIMARY KEY,
            lang TEXT NOT NULL CHECK (lang IN ('ru','kz','en')),
            joined_at {timestamp} NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''',
        f'''CREATE TABLE IF NOT EXISTS report_feedback (
            user_id BIGINT NOT NULL,
            report_id TEXT NOT NULL REFERENCES report_explanations(id) ON DELETE CASCADE,
            useful INTEGER NOT NULL CHECK (useful IN (0,1)),
            updated_at {timestamp} NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id,report_id)
        )''',
        'CREATE INDEX IF NOT EXISTS idx_report_feedback_report ON report_feedback(report_id)',
    ):
        db.execute_query(conn, sql)
    conn.commit()


def join_pilot(user_id: int, lang: str) -> None:
    if user_id <= 0 or lang not in ('ru', 'kz', 'en'):
        raise ValueError('invalid participant')
    with closing(db.get_connection()) as conn, conn:
        db.execute_query(conn, '''INSERT INTO pilot_participants(user_id,lang) VALUES (?,?)
            ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang''', (user_id,lang))


def pilot_status(user_id: int) -> dict:
    with closing(db.get_connection()) as conn:
        joined = db.execute_query(conn, 'SELECT joined_at FROM pilot_participants WHERE user_id=?', (user_id,)).fetchone()
        feedback = db.execute_query(conn, '''SELECT COUNT(*),COALESCE(SUM(useful),0)
            FROM report_feedback WHERE user_id=?''', (user_id,)).fetchone()
    return {'joined': bool(joined), 'reviews': int(feedback[0]), 'useful': int(feedback[1])}


def save_feedback(user_id: int, report_id: str, useful: bool) -> bool:
    if not isinstance(useful, bool) or user_id <= 0 or len(report_id) != 32:
        raise ValueError('invalid feedback')
    with closing(db.get_connection()) as conn, conn:
        cursor = db.execute_query(conn, '''INSERT INTO report_feedback(user_id,report_id,useful)
            SELECT ?,id,? FROM report_explanations WHERE id=? AND user_id=?
            ON CONFLICT(user_id,report_id) DO UPDATE
            SET useful=excluded.useful,updated_at=CURRENT_TIMESTAMP''',
            (user_id,int(useful),report_id,user_id))
        return cursor.rowcount == 1


def leave_pilot(user_id: int) -> None:
    with closing(db.get_connection()) as conn, conn:
        db.execute_query(conn, 'DELETE FROM report_feedback WHERE user_id=?', (user_id,))
        db.execute_query(conn, 'DELETE FROM pilot_participants WHERE user_id=?', (user_id,))


def pilot_summary() -> dict:
    """Internal aggregate only. An application is interest, not verified adoption."""
    with closing(db.get_connection()) as conn:
        joined = db.execute_query(conn, 'SELECT COUNT(*) FROM pilot_participants').fetchone()[0]
        reviewers, reviews, helpful = db.execute_query(conn, '''SELECT COUNT(DISTINCT f.user_id),
            COUNT(*),COALESCE(SUM(f.useful),0) FROM report_feedback f
            INNER JOIN pilot_participants p ON p.user_id=f.user_id''').fetchone()
    return {'applications': int(joined), 'participants_with_feedback': int(reviewers),
            'rated_reports': int(reviews), 'helpful_reports': int(helpful)}
