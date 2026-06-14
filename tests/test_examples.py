import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUZZY = ROOT / "fuzzy.py"


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(FUZZY), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_quick_start_words_example_works():
    result = run_cli("pytohn", "words.txt", "--no-color", "--top", "1")

    assert result.returncode == 0
    assert "Best match:" in result.stdout
    assert "python" in result.stdout
    assert "file not found" not in result.stderr


def test_csv_example_works():
    result = run_cli("Jon Smith", "names.csv", "-c", "2", "--threshold", "70", "--csv")

    assert result.returncode == 0
    rows = list(csv.reader(result.stdout.splitlines()))
    assert rows[0] == ["rank", "score", "match"]
    assert any(row[2] == "John Smith" for row in rows[1:])


def test_tsv_example_works():
    result = run_cli("Jon Smith", "names.tsv", "-c", "2", "--threshold", "70", "--csv")

    assert result.returncode == 0
    rows = list(csv.reader(result.stdout.splitlines()))
    assert rows[0] == ["rank", "score", "match"]
    assert any(row[2] == "John Smith" for row in rows[1:])
