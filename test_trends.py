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
        "INSERT OR IGNORE INTO messages (channel, message_id, date, text, views, is_forward, media_type, scraped_at) VALUES (?,?,?,?,?,?,?,?)",
        (channel, message_id, date, text, views, 0, None, now.isoformat()),
    )
    conn.commit()


def test_tokenize_drops_stopwords_and_short_tokens():
    tokens = trends._tokenize("The dog and the cat are playing in the park")
    assert "the" not in tokens
    assert "and" not in tokens
    assert "in" not in tokens
    assert "dog" in tokens
    assert "playing" in tokens


def test_tokenize_strips_urls_and_mentions():
    tokens = trends._tokenize("Check this out https://example.com/foo @somechannel report")
    assert not any("http" in t or "example" in t for t in tokens)
    assert "somechannel" not in tokens
    assert "report" in tokens


def test_terms_includes_bigrams():
    terms = trends._terms("Berlin transit authority goes on strike today")
    assert "transit authority" in terms
    assert "authority" in terms


def test_new_term_with_zero_baseline_requires_min_channels(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # same novel phrase, but only on 2 channels
        _insert_message(conn, "chan_a", 1, "Unique special bulletin about the incident", hours_ago=1)
        _insert_message(conn, "chan_b", 2, "Unique special bulletin about the incident", hours_ago=1)

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
            _insert_message(conn, chan, i, "Breaking special report about the incident today", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=3, min_channels=3, as_of=as_of,
        )

    # Every word/bigram here comes from the exact same post on the same 4
    # channels, so the diversity filter should collapse them to a single
    # representative instead of listing every fragment separately.
    assert len(results) == 1
    assert results[0]["channel_count"] == 4


def test_term_with_high_baseline_is_not_treated_as_new_spike(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # heavy, steady baseline mentions of "ongoingsaga" across the week
        for i in range(30):
            _insert_message(conn, f"chan_{i % 5}", 1000 + i, f"The ongoingsaga continues today, part {i}", hours_ago=24 + i * 4)
        # only a mild uptick in the recent window — same rate as usual, not a spike
        for i, chan in enumerate(["chan_a", "chan_b", "chan_c"]):
            _insert_message(conn, chan, i, "The ongoingsaga continues today", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=1, min_channels=3, as_of=as_of,
        )

    # a term mentioned at roughly its normal rate should score near 1x, not read as a spike
    # (all fragments of this post collapse to one representative — check whichever survives)
    assert results
    assert all(r["score"] < 1.5 for r in results)


def test_diverse_stories_are_not_collapsed_together(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # one viral, wordy post on 4 channels
        for i, chan in enumerate(["chan_a", "chan_b", "chan_c", "chan_d"]):
            _insert_message(conn, chan, i, "Politician announces surprising resignation amid scandal today", hours_ago=1)
        # a second, unrelated story on a different set of 4 channels
        for i, chan in enumerate(["chan_e", "chan_f", "chan_g", "chan_h"]):
            _insert_message(conn, chan, 100 + i, "Central bank raises interest rates sharply again", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=3, min_channels=3, as_of=as_of, top_n=20,
        )

    # two unrelated stories should produce (at least) two distinct survivors,
    # not have the second story's terms crowded out by the first's fragments
    assert len(results) >= 2


def test_diagnose_baseline_warns_when_history_is_too_thin(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # a burst of fresh scraping, but almost nothing in the week before it
        for i in range(50):
            _insert_message(conn, f"chan_{i % 10}", i, "Some fresh report today", hours_ago=1)
        _insert_message(conn, "chan_0", 9999, "One old message", hours_ago=100)

        warning = trends.diagnose_baseline(recent_hours=24, baseline_hours=168, as_of=as_of)

    assert warning is not None
    assert "scraper.py --hours 168" in warning


def test_diagnose_baseline_silent_with_healthy_history(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # comparable volume in both the recent window and the baseline before it
        for i in range(20):
            _insert_message(conn, f"chan_{i % 5}", i, "Some fresh report today", hours_ago=1)
        for i in range(120):
            _insert_message(conn, f"chan_{i % 5}", 1000 + i, "Some older report", hours_ago=30 + i)

        warning = trends.diagnose_baseline(recent_hours=24, baseline_hours=168, as_of=as_of)

    assert warning is None


def test_zero_baseline_term_is_marked_new(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i, ch in enumerate(["a", "b", "c"]):
            _insert_message(conn, ch, i, "Zeppelin sighting reported downtown", hours_ago=1)
        _insert_message(conn, "a", 10, "Regular harbour update", hours_ago=60)
        for i, ch in enumerate(["a", "b", "c"]):
            _insert_message(conn, ch, 20 + i, "Regular harbour update", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    # Terms from the same posts collapse to one (e.g. only "sighting"
    # survives of zeppelin/sighting/...), so find each by its example post.
    zeppelin = next(r for r in results if "Zeppelin" in r["examples"][0]["text"])
    harbour = next(r for r in results if "harbour" in r["examples"][0]["text"])
    assert zeppelin["is_new"] is True
    assert harbour["is_new"] is False


def test_same_channel_repost_counts_once(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i, ch in enumerate(["a", "b", "c"]):
            _insert_message(conn, ch, i, "Zeppelin sighting reported downtown", hours_ago=2)
        # channel a re-posts it twice more the same day
        _insert_message(conn, "a", 10, "Zeppelin sighting reported downtown", hours_ago=1)
        _insert_message(conn, "a", 11, "Zeppelin  sighting reported downtown!", hours_ago=0.5)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    assert results and all(r["recent_count"] == 3 for r in results)
    for r in results:
        channels = [ex["channel"] for ex in r["examples"]]
        assert len(channels) == len(set(channels))


def test_new_terms_rank_by_channel_count(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        # "quokka": many mentions, few channels
        for i in range(8):
            _insert_message(conn, ["a", "b", "c"][i % 3], i, f"Quokka report number {i}", hours_ago=1)
        # "walrus": fewer mentions, more channels
        for i, ch in enumerate(["d", "e", "f", "g", "h"]):
            _insert_message(conn, ch, 100 + i, "Walrus escapes zoo", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    assert "Walrus" in results[0]["examples"][0]["text"]


def test_detail_keys_are_exact_posts(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i, ch in enumerate(["a", "b", "c"]):
            _insert_message(conn, ch, i, "Produkt alle ausverkauft", hours_ago=1)
        _insert_message(conn, "d", 9, "Allerdings in Halle nichts Neues", hours_ago=1)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    assert results[0]["message_keys"] == {("a", 0), ("b", 1), ("c", 2)}


def test_new_term_reports_first_seen(tmp_path):
    db_path = _setup_db(tmp_path)
    as_of = datetime.now(timezone.utc)
    with patch.object(db, "DB_PATH", db_path):
        conn = db.get_conn()
        for i, (ch, h) in enumerate([("a", 14), ("b", 5), ("c", 2)]):
            _insert_message(conn, ch, i, "Zeppelin sighting reported downtown", hours_ago=h)

        results = trends.get_trending_terms(
            recent_hours=24, baseline_hours=168, min_recent_count=2, min_channels=3, as_of=as_of,
        )

    assert trends.format_ago(results[0]["first_seen"], as_of) == "14h ago"


def test_format_ago_uses_minutes_under_an_hour():
    now = datetime.now(timezone.utc)
    assert trends.format_ago((now - timedelta(minutes=45)).isoformat(), now) == "45m ago"
