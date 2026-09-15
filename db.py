"""
SQLite schema and helpers for storing scraped messages.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "messages.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY,
                channel     TEXT NOT NULL,
                tier        TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                date        TEXT NOT NULL,
                text        TEXT,
                views       INTEGER DEFAULT 0,
                is_forward  INTEGER DEFAULT 0,
                media_type  TEXT,
                scraped_at  TEXT NOT NULL,
                UNIQUE(channel, message_id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
            CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
        """)


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
