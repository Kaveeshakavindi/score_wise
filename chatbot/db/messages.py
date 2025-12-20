from __future__ import annotations
from uuid import uuid4
from db.conn import get_conn

def save_message(session_id: str, role: str, content: str) -> None:
    message_id = uuid4()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages (id, session_id, role, content)
                VALUES (%s, %s, %s, %s)
                """,
                (message_id, session_id, role, content),
            )
        conn.commit()

def load_history(session_id: str) -> list[tuple[str, str]]:
    """
    Returns list of (role, content): from oldest -> newest
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    return [(_to_prompt_role(r[0]), r[1]) for r in rows]

def load_last_exchange(session_id: str) -> tuple[str | None, str | None]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT 2
                """,
                (session_id,),
            )
            rows = cur.fetchall()
    if not rows:
        return None, None
    last_user = None
    last_assistant = None
    for role, content in rows:
        if role == "user" and last_user is None:
            last_user = content
        elif role == "assistant" and last_assistant is None:
            last_assistant = content
    return last_user, last_assistant

def _to_prompt_role(role: str) -> str:
    if role == "user":
        return "human"
    if role == "assistant":
        return "ai"
    return role
