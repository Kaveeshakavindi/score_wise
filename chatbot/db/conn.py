import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

def get_conn() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)

