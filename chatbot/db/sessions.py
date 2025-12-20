from __future__ import annotations
from uuid import uuid4
from db.conn import get_conn

def create_session(user_id: str) -> str:
    session_id = str(uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_sessions (id, user_id)
                VALUES (%s, %s)
                """,
                (session_id, user_id),
            )
        conn.commit()
    return session_id

def list_sessions(user_id: str) -> list[tuple[str, str | None]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title
                FROM chat_sessions
                WHERE user_id = %s
                ORDER BY last_active DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        session_id = str(row[0])
        title = row[1]
        result.append((session_id, title))
    return result

def set_session_title(session_id: str, title: str) -> None:
    if not title:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE chat_sessions
                SET title = %s
                WHERE id = %s AND title IS NULL
                """,
                (title, session_id),
            )
        conn.commit()

def touch_session(session_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET last_active = now() WHERE id = %s",
                (session_id,),
            )
        conn.commit()

def delete_session(session_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE id = %s",
                (session_id,),
            )
        conn.commit()

def delete_all_sessions(user_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_sessions WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()
