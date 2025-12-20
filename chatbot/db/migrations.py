from pathlib import Path
from db.conn import get_conn

def run_schema() -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    sql = schema_path.read_text("utf-8")
    
    with get_conn() as conn:
        with conn.cursor() as cur: 
            cur.execute(sql)
        conn.commit()
    