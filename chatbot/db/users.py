from __future__ import annotations
from uuid import uuid4
import bcrypt
from db.conn import get_conn

def create_user(name: str, nickname: str, password: str, age: int) -> None: 
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
        ).decode("utf-8")
    user_id = uuid4()
    
    with get_conn() as conn: 
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, name, nickname, password_hash, age)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, name, nickname, password_hash, age),
            )
        conn.commit()

def auth_user(nickname: str, password: str) -> str | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash FROM users WHERE nickname = %s",
                (nickname,),
            )
            row = cur.fetchone()
    if not row:
        return None
    
    user_id, password_hash = row
    ok = bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    return str(user_id) if ok else None

def user_exists(nickname: str) -> bool:
    with get_conn() as conn: 
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE nickname=%s", (nickname,))
            return cur.fetchone() is not None

def get_user_profile(user_id: str) -> dict[str, str | int] | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name, nickname, age
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    name, nickname, age = row
    return {"name": name, "nickname": nickname, "age": age}
