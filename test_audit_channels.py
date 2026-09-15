from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import audit_channels
import channels
import db


def _setup_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
    return db_path


def _insert_message(conn, channel, message_id, days_ago=1):
    date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO messages (channel, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?)",
        (channel, message_id, date, "some text", 0, 0, None, date),
    )
    conn.commit()


def _set_found(conn, channel, found: bool):
    conn.execute(
        "INSERT INTO channel_status (channel, found, checked_at) VALUES (?, ?, ?)",
        (channel, 1 if found else 0, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def test_channel_with_no_messages_is_dead(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path), patch.object(audit_channels, "get_all_monitored", return_value=["ghost_channel"]):
        result = audit_channels.audit()

    assert [h for h, _ in result["dead"]] == ["ghost_channel"]
    assert result["unreachable"] == []
    assert result["active"] == []


def test_channel_confirmed_unreachable_on_last_check(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "gone_channel", 1, days_ago=90)
        _set_found(conn, "gone_channel", found=False)

    with patch.object(db, "DB_PATH", db_path), patch.object(audit_channels, "get_all_monitored", return_value=["gone_channel"]):
        result = audit_channels.audit()

    assert result["dead"] == []
    assert [h for h, _ in result["unreachable"]] == ["gone_channel"]
    assert result["active"] == []


def test_channel_with_old_post_but_still_reachable_is_active(tmp_path):
    """A channel that simply hasn't posted in a while is NOT a problem —
    only a confirmed-gone page (found=False) should be flagged."""
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "quiet_but_fine", 1, days_ago=90)
        _set_found(conn, "quiet_but_fine", found=True)

    with patch.object(db, "DB_PATH", db_path), patch.object(audit_channels, "get_all_monitored", return_value=["quiet_but_fine"]):
        result = audit_channels.audit()

    assert result["unreachable"] == []
    assert [h for h, _ in result["active"]] == ["quiet_but_fine"]


def test_channel_never_checked_is_active_not_unreachable(tmp_path):
    """No channel_status row at all means we've never confirmed either way
    — that's not evidence of a problem, so it shouldn't be flagged."""
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "never_checked", 1, days_ago=1)

    with patch.object(db, "DB_PATH", db_path), patch.object(audit_channels, "get_all_monitored", return_value=["never_checked"]):
        result = audit_channels.audit()

    assert result["unreachable"] == []
    assert [h for h, _ in result["active"]] == ["never_checked"]


def test_channel_below_min_msgs_is_low_even_if_recent(tmp_path):
    db_path = _setup_db(tmp_path)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        _insert_message(conn, "sparse_channel", 1, days_ago=1)

    with patch.object(db, "DB_PATH", db_path), patch.object(audit_channels, "get_all_monitored", return_value=["sparse_channel"]):
        result = audit_channels.audit(min_msgs=5)

    assert [h for h, _ in result["low"]] == ["sparse_channel"]
    assert result["active"] == []
    assert result["unreachable"] == []


def test_prune_removes_given_handles_only(tmp_path):
    registry_path = tmp_path / "channels.csv"
    registry_path.write_text("handle\ndead_one\nkeep_one\n", encoding="utf-8")

    with patch.object(audit_channels, "REGISTRY_PATH", registry_path), \
         patch.object(channels, "REGISTRY_PATH", registry_path):
        audit_channels.prune([("dead_one", 0)])
        remaining = channels.load_channels()

    assert remaining == ["keep_one"]
