import channels as ch


def _write_csv(tmp_path, rows):
    path = tmp_path / "channels.csv"
    lines = ["handle,tier"] + [f"{h},{t}" for h, t in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_load_channels_reads_csv(tmp_path):
    path = _write_csv(tmp_path, [("chan_a", "tier1"), ("chan_b", "tier2")])
    result = ch.load_channels(path)
    assert result == [("chan_a", "tier1"), ("chan_b", "tier2")]


def test_load_channels_missing_file_returns_empty(tmp_path):
    result = ch.load_channels(tmp_path / "does_not_exist.csv")
    assert result == []


def test_load_channels_skips_blank_handles(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("handle,tier\nchan_a,tier1\n,tier2\n", encoding="utf-8")
    result = ch.load_channels(path)
    assert result == [("chan_a", "tier1")]


def test_load_channels_without_tier_column(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("handle\nchan_a\nchan_b\n", encoding="utf-8")
    result = ch.load_channels(path)
    assert result == [("chan_a", ""), ("chan_b", "")]


def test_load_channels_with_blank_tier_cells(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("handle,tier\nchan_a,\nchan_b,core\n", encoding="utf-8")
    result = ch.load_channels(path)
    assert result == [("chan_a", ""), ("chan_b", "core")]


def test_get_all_monitored_returns_given_list():
    given = [("chan_a", "tier1"), ("chan_b", "tier2")]
    assert ch.get_all_monitored(given) == given


def test_get_tiers_returns_sorted_distinct_labels():
    given = [("chan_a", "tier1"), ("chan_b", "tier2"), ("chan_c", "tier1")]
    assert ch.get_tiers(given) == ["tier1", "tier2"]


def test_get_tiers_with_arbitrary_labels():
    given = [("chan_a", "core"), ("chan_b", "watch")]
    assert ch.get_tiers(given) == ["core", "watch"]
