import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import db


def make_temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
    return db_path


def test_init_creates_messages_table(tmp_path):
    db_path = make_temp_db(tmp_path)
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "messages" in tables


def test_init_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
        db.init_db()  # should not raise


def test_messages_unique_constraint(tmp_path):
    db_path = make_temp_db(tmp_path)
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    row = ("channel_a", 42, now, "hello", 100, 0, None, now)
    conn.execute(
        "INSERT INTO messages (channel, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?)",
        row,
    )
    conn.commit()

    # Second insert of same (channel, message_id) should be ignored
    conn.execute(
        "INSERT OR IGNORE INTO messages (channel, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?)",
        row,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert count == 1


def test_get_conn_creates_data_dir(tmp_path):
    nested = tmp_path / "a" / "b" / "messages.db"
    with patch.object(db, "DB_PATH", nested):
        conn = db.get_conn()
        conn.close()
    assert nested.exists()
