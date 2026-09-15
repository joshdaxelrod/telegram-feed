import channels as ch


def test_load_channels_reads_csv(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("handle\nchan_a\nchan_b\n", encoding="utf-8")
    result = ch.load_channels(path)
    assert result == ["chan_a", "chan_b"]


def test_load_channels_missing_file_returns_empty(tmp_path):
    result = ch.load_channels(tmp_path / "does_not_exist.csv")
    assert result == []


def test_load_channels_skips_blank_handles(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("handle\nchan_a\n\n", encoding="utf-8")
    result = ch.load_channels(path)
    assert result == ["chan_a"]


def test_get_all_monitored_returns_given_list():
    given = ["chan_a", "chan_b"]
    assert ch.get_all_monitored(given) == given
