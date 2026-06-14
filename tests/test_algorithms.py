import pytest

from fuzzy import (
    highlight,
    jaro,
    jaro_score,
    jaro_winkler_score,
    levenshtein,
    levenshtein_score,
    score_bar,
)


def test_levenshtein_distance_examples():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3
    assert levenshtein("same", "same") == 0


def test_levenshtein_score_examples():
    assert levenshtein_score("kitten", "sitting") == 57.1
    assert levenshtein_score("", "") == 100.0
    assert levenshtein_score("abc", "abc") == 100.0


def test_jaro_examples():
    assert round(jaro("MARTHA", "MARHTA"), 3) == 0.944
    assert jaro_score("MARTHA", "MARHTA") == 94.4
    assert jaro_score("", "abc") == 0.0
    assert jaro_score("abc", "abc") == 100.0


def test_jaro_winkler_examples():
    assert jaro_winkler_score("MARTHA", "MARHTA") == 96.1
    assert jaro_winkler_score("DIXON", "DICKSONX") == 81.3
    assert jaro_winkler_score("abc", "xyz") == 0.0


def test_highlight_without_color_is_plain_text():
    assert highlight("Python", "py", color=False) == "Python"


def test_highlight_with_color_adds_ansi_codes():
    result = highlight("Python", "py", color=True)
    assert "\x1b[" in result
    assert result.endswith("on")


def test_score_bar_without_color_has_expected_width():
    bar = score_bar(50, width=10, color=False)
    assert bar == "█████░░░░░"
    assert len(bar) == 10
