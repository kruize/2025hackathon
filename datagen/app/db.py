import sqlite3
from .constants import DB_PATH
from .queries import CREATE_TABLES

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        for ddl in CREATE_TABLES:
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()
