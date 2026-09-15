from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import db
import trends


def _setup_db(tmp_path):
    db_path = tmp_path / "test.db"
    with patch.object(db, "DB_PATH", db_path):
        db.init_db()
    return db_path


def _insert_message(conn, channel, message_id, text, hours_ago, views=100):
    now = datetime.now(timezone.utc)
    date = (now - timedelta(hours=hours_ago)).isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO messages (channel, tier, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (channel, "tier1", message_id, date, text, views, 0, None, now.isoformat()),
    )
    conn.commit()


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = trends._tokenize("Der Hund und die Katze laufen im Park")
    assert "der" not in tokens
    assert "und" not in tokens
    assert "im" not in tokens
    assert "hund" in tokens
    assert "katze" in tokens


def test_tokenize_strips_urls_and_mentions():
    tokens = trends._tokenize("Schau mal https://example.com/foo @somechannel Bericht")
    assert not any("http" in t or "example" in t for t in tokens)
    assert "somechannel" not in tokens
    assert "bericht" in tokens


def test_terms_includes_bigrams():
    terms = trends._terms("Berliner Verkehrsbetriebe streiken heute")
    assert "berliner verkehrsbetriebe" in terms
    assert "verkehrsbetriebe" in terms


def test_new_term_with_zero_baseline_requires_min_channels(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # same novel phrase, but only on 2 channels
        _insert_message(conn, "chan_a", 1, "Einzigartige Sondermeldung zum Vorfall", hours_ago=1)
        _insert_message(conn, "chan_b", 2, "Einzigartige Sondermeldung zum Vorfall", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    assert results == []


def test_term_trending_across_enough_channels_is_found(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i, chan in enumerate(["chan_a", "chan_b", "chan_c", "chan_d"]):
            _insert_message(conn, chan, i, "Sonderbericht Vorfall breaking news heute", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=3, min_channels=3, as_of=as_of,
        )

    terms = {r["term"] for r in results}
    assert "sonderbericht" in terms
    top = next(r for r in results if r["term"] == "sonderbericht")
    assert top["channel_count"] == 4


def test_term_with_high_baseline_is_not_treated_as_new_spike(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # heavy, steady baseline mentions of "dauerthema" across the week
        for i in range(30):
            _insert_message(conn, f"chan_{i % 5}", 1000 + i, "Dauerthema wird diskutiert", hours_ago=24 + i * 4)
        # only a mild uptick in the recent window — same rate as usual, not a spike
        for i, chan in enumerate(["chan_a", "chan_b", "chan_c"]):
            _insert_message(conn, chan, i, "Dauerthema wird diskutiert", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=1, min_channels=3, as_of=as_of,
        )

    dauerthema = next(r for r in results if r["term"] == "dauerthema")
    # a term mentioned at roughly its normal rate should score near 1x, not read as a spike
    assert dauerthema["score"] < 1.5


def test_respects_tier_filter(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        conn.execute(
            "INSERT INTO messages (channel, tier, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("chan_x", "tier2", 1, (as_of - timedelta(hours=1)).isoformat(), "Exklusivbericht Sonderthema heute", 100, 0, None, as_of.isoformat()),
        )
        conn.commit()

        results = trends.get_trending_terms(
            recent_hours=24, tier="tier1", min_recent_count=1, min_channels=1, as_of=as_of,
        )

    assert results == []
