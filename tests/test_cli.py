import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUZZY = ROOT / "fuzzy.py"


def run_cli(*args, input_text=None):
    return subprocess.run(
        [sys.executable, str(FUZZY), *args],
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_returns_best_match_from_file(tmp_path):
    words = tmp_path / "words.txt"
    words.write_text("python\npytest\npyright\n", encoding="utf-8")

    result = run_cli("pytohn", str(words), "-n", "1", "--no-color")

    assert result.returncode == 0
    assert "Best match:" in result.stdout
    assert "python" in result.stdout
    assert "\x1b[" not in result.stdout


def test_cli_can_read_from_stdin_as_csv():
    result = run_cli(
        "Jon Smith",
        "-c",
        "2",
        "--threshold",
        "70",
        "--csv",
        input_text="id,name\n1,John Smith\n2,Jane Doe\n",
    )

    assert result.returncode == 0
    rows = list(csv.reader(result.stdout.splitlines()))
    assert rows[0] == ["rank", "score", "match"]
    assert rows[1][2] == "John Smith"


def test_cli_ignore_case_uses_casefold_matching(tmp_path):
    words = tmp_path / "words.txt"
    words.write_text("STRASSE\nOther\n", encoding="utf-8")

    result = run_cli("straße", str(words), "-n", "1", "-i", "--csv")

    assert result.returncode == 0
    assert "STRASSE" in result.stdout
    assert "100.0" in result.stdout


def test_cli_rejects_invalid_top():
    result = run_cli("test", "--top", "0", input_text="test\n")

    assert result.returncode != 0
    assert "must be greater than 0" in result.stderr


def test_cli_rejects_invalid_threshold():
    result = run_cli("test", "--threshold", "101", input_text="test\n")

    assert result.returncode != 0
    assert "must be between 0 and 100" in result.stderr


def test_cli_rejects_invalid_column():
    result = run_cli("test", "--col", "0", input_text="test\n")

    assert result.returncode != 0
    assert "must be 1 or greater" in result.stderr


def test_cli_missing_file_returns_error():
    result = run_cli("test", "missing-file.txt")

    assert result.returncode == 1
    assert "file not found" in result.stderr


def test_cli_empty_input_warns_without_failure():
    result = run_cli("test", input_text="")

    assert result.returncode == 0
    assert "word list is empty" in result.stderr
