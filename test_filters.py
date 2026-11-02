from unittest.mock import patch

import filters


def _local(tmp_path, content):
    path = tmp_path / "filters.local.txt"
    path.write_text(content, encoding="utf-8")
    with patch.object(filters, "LOCAL_FILTERS_PATH", path):
        return filters._load_local_patterns()


def test_plain_line_matches_as_literal_substring(tmp_path):
    patterns = _local(tmp_path, "kopp-verlag.de\n")
    assert patterns[0].search("Bestellen bei KOPP-VERLAG.DE")
    assert not patterns[0].search("koppXverlag.de")


def test_re_line_is_regex_matched_per_line(tmp_path):
    patterns = _local(tmp_path, "# note\nre:^\\W*anzeige\\W*$\n")
    assert len(patterns) == 1
    assert patterns[0].search("Super Angebot\n (Anzeige)\nJetzt")
    assert not patterns[0].search("Sie erstattete Anzeige bei der Polizei")
    assert not patterns[0].search("Strafanzeige gestellt")
