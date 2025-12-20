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

def list_sessions(user_id: str) -> list[tuple[str, str, str, str | None]]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cs.id, cs.created_at, cs.last_active, lm.role, lm.content
                FROM chat_sessions cs
                LEFT JOIN LATERAL (
                    SELECT role, content
                    FROM messages
                    WHERE session_id = cs.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) lm ON true
                WHERE cs.user_id = %s
                ORDER BY cs.last_active DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    result = []
    for row in rows:
        session_id = str(row[0])
        created_at = row[1].isoformat(sep=" ", timespec="seconds")
        last_active = row[2].isoformat(sep=" ", timespec="seconds")
        role = row[3]
        content = row[4]
        if role and content:
            preview = f"{role}: {content}"
        else:
            preview = None
        result.append((session_id, created_at, last_active, preview))
    return result

def touch_session(session_id: str) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chat_sessions SET last_active = now() WHERE id = %s",
                (session_id,),
            )
        conn.commit()
