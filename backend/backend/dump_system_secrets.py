
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'system_secrets.db')
sys.path.insert(0, os.path.dirname(__file__))
from backend import settings

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def dump_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    print("Tables:")
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    for (table,) in tables:
        print(f"\nTable: {table}")
        try:
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            for row in rows:
                print(row)
                # Always try to decrypt secrets table keys
                if table == 'secrets':
                    # Support both (id, key, value) and (key, value)
                    if len(row) == 3:
                        _, key, value = row
                    elif len(row) == 2:
                        key, value = row
                    else:
                        continue
                    if key in ('db_user', 'db_name', 'db_password'):
                        try:
                            plain = settings.decrypt_value(value)
                            print(f"  [DECRYPTED] {key}: {plain}")
                        except Exception as e:
                            print(f"  [DECRYPT ERROR] {key}: {e}")
        except Exception as e:
            print(f"Error reading table {table}: {e}")
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        init_db()
        print('Initialized system_secrets.db and created tables.')
    else:
        dump_db()