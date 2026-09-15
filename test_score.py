import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import db
import score


def _setup_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
    return db_path


def _insert_message(conn, channel, message_id, views, hours_ago=1, is_forward=0, text="Some claim about politics"):
    now = datetime.now(timezone.utc)
    date = (now - timedelta(hours=hours_ago)).isoformat()
    scraped_at = now.isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO messages (channel, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?)",
        (channel, message_id, date, text, views, is_forward, None, scraped_at),
    )
    conn.commit()


def test_virality_score_returns_views():
    assert score.virality_score(views=1000) == 1000.0


def test_virality_score_zero():
    assert score.virality_score(views=0) == 0.0


def test_virality_score_higher_views_ranks_higher():
    s1 = score.virality_score(views=1000)
    s2 = score.virality_score(views=5000)
    assert s2 > s1


def test_get_top_messages_returns_sorted_by_virality(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "low_views", 1, views=1000)
        _insert_message(conn, "high_views", 2, views=50000)
        _insert_message(conn, "mid_views", 3, views=10000)

        results = score.get_top_messages(hours=24)

    assert results[0]["channel"] == "high_views"
    assert all(r["virality_score"] >= results[i + 1]["virality_score"] for i, r in enumerate(results[:-1]))


def test_get_top_messages_deduplicates_same_text(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        shared_text = "Die Regierung hat 97% der Bevölkerung belogen laut neuer Studie"
        _insert_message(conn, "chan_a", 1, views=5000, text=shared_text)
        _insert_message(conn, "chan_b", 2, views=3000, text=shared_text)
        _insert_message(conn, "chan_c", 3, views=2000, text="Completely different claim here")

        results = score.get_top_messages(hours=24)

    assert len(results) == 2
    shared = next(r for r in results if r["channel_count"] == 2)
    assert shared["channel"] in ("chan_a", "chan_b")
    single = next(r for r in results if r["channel"] == "chan_c")
    assert single["channel_count"] == 1


def test_get_top_messages_respects_hours_window(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "recent", 1, views=5000, hours_ago=1)
        _insert_message(conn, "old", 2, views=5000, hours_ago=48)

        results = score.get_top_messages(hours=24)

    channels = [r["channel"] for r in results]
    assert "recent" in channels
    assert "old" not in channels


def test_get_top_messages_excludes_empty_text(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "no_text", 1, views=10000, text="")
        _insert_message(conn, "has_text", 2, views=5000, text="A real claim")

        results = score.get_top_messages(hours=24)

    channels = [r["channel"] for r in results]
    assert "no_text" not in channels
    assert "has_text" in channels


def test_get_random_messages_respects_hours_window(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "recent", 1, views=100, hours_ago=1)
        _insert_message(conn, "old", 2, views=100, hours_ago=48)

        results = score.get_random_messages(hours=24, seed=1)

    channels = [r["channel"] for r in results]
    assert "recent" in channels
    assert "old" not in channels


def test_get_random_messages_respects_limit(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i in range(10):
            _insert_message(conn, f"chan_{i}", i, views=100)

        results = score.get_random_messages(hours=24, limit=3, seed=1)

    assert len(results) == 3


def test_get_random_messages_same_seed_is_reproducible(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i in range(10):
            _insert_message(conn, f"chan_{i}", i, views=100)

        first = score.get_random_messages(hours=24, seed=42)
        second = score.get_random_messages(hours=24, seed=42)

    assert [r["channel"] for r in first] == [r["channel"] for r in second]


def test_get_spotlight_messages_one_per_channel(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "chan_a", 1, views=100)
        _insert_message(conn, "chan_a", 2, views=5000)  # chan_a's top post
        _insert_message(conn, "chan_b", 3, views=200)

        results = score.get_spotlight_messages(hours=24, per_channel=1, seed=1)

    by_channel = {r["channel"]: r for r in results}
    assert len(results) == 2
    assert by_channel["chan_a"]["views"] == 5000


def test_get_spotlight_messages_small_channel_not_crowded_out(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # chan_big posts many high-view messages
        for i in range(20):
            _insert_message(conn, "chan_big", i, views=100000)
        # chan_small posts one modest message
        _insert_message(conn, "chan_small", 100, views=50)

        results = score.get_spotlight_messages(hours=24, per_channel=1, seed=1)

    channels = {r["channel"] for r in results}
    assert "chan_small" in channels
    assert "chan_big" in channels


def test_get_spotlight_messages_per_channel_limit(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i in range(5):
            _insert_message(conn, "chan_a", i, views=100 * i)

        results = score.get_spotlight_messages(hours=24, per_channel=2, limit=None, seed=1)

    assert len(results) == 2
    assert sorted(r["views"] for r in results) == [300, 400]
