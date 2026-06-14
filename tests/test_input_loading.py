import io

from fuzzy import detect_delimiter, load_words


def test_load_plain_word_list():
    source = io.StringIO("python\npytest\n\npyright\n")
    assert load_words(source, col=1) == ["python", "pytest", "pyright"]


def test_load_csv_column_one_is_parsed_as_csv_not_plain_line():
    source = io.StringIO("id,name\n1,John Smith\n2,Jane Doe\n")
    assert load_words(source, col=1) == ["id", "1", "2"]


def test_load_csv_column_two():
    source = io.StringIO("id,name\n1,John Smith\n2,Jane Doe\n")
    assert load_words(source, col=2) == ["name", "John Smith", "Jane Doe"]


def test_load_tsv_column_two():
    source = io.StringIO("id\tname\n1\tJohn Smith\n2\tJane Doe\n")
    assert load_words(source, col=2) == ["name", "John Smith", "Jane Doe"]


def test_missing_column_is_skipped():
    source = io.StringIO("id,name\n1\n2,Jane Doe\n")
    assert load_words(source, col=2) == ["name", "Jane Doe"]


def test_detect_delimiter_returns_none_for_plain_text_column_one():
    assert detect_delimiter(["python", "pytest"], col=1) is None


def test_detect_delimiter_assumes_comma_for_requested_column_without_delimiter():
    assert detect_delimiter(["python", "pytest"], col=2) == ","
