#!/usr/bin/env python3
"""
fuzzy.py — Levenshtein / Jaro / Jaro-Winkler fuzzy string matcher.

Usage:
    fuzzy.py <query> [options] [wordlist_file]

If no file is given, reads the word list from stdin, one word per line.

Examples:
    fuzzy.py "helo wrold" words.txt
    fuzzy.py "pytohn" words.txt -n 5 -a jaro_winkler
    cat names.csv | fuzzy.py "Jon Smith" -c 2 --threshold 70
    fuzzy.py "nginx" /etc/hosts -i
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Callable, Sequence

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN = "\x1b[36m"
RED = "\x1b[31m"

NO_COLOR = {
    "reset": "",
    "bold": "",
    "dim": "",
    "green": "",
    "yellow": "",
    "cyan": "",
    "red": "",
}

ANSI_COLOR = {
    "reset": RESET,
    "bold": BOLD,
    "dim": DIM,
    "green": GREEN,
    "yellow": YELLOW,
    "cyan": CYAN,
    "red": RED,
}


def palette(enabled: bool) -> dict[str, str]:
    return ANSI_COLOR if enabled else NO_COLOR


def supports_pretty_glyphs(stream: object) -> bool:
    """Return whether a text stream can encode the CLI's pretty glyphs."""
    encoding = getattr(stream, "encoding", None)
    if not encoding:
        return False

    try:
        "─█░".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False

    return True


# ── Algorithms, zero runtime dependencies ────────────────────────────────────

def levenshtein(a: str, b: str) -> int:
    """Return Levenshtein edit distance using O(m·n) time and O(min(m,n)) space."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Keep the shorter string on the DP row axis to reduce memory usage.
    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, char_b in enumerate(b, 1):
            substitution_cost = 0 if char_a == char_b else 1
            current[j] = min(
                previous[j] + 1,                  # deletion
                current[j - 1] + 1,               # insertion
                previous[j - 1] + substitution_cost,  # substitution
            )
        previous = current

    return previous[-1]


def levenshtein_score(a: str, b: str) -> float:
    """Return Levenshtein similarity as a 0-100 score."""
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 100.0

    distance = levenshtein(a, b)
    return round((1 - distance / max_len) * 100, 1)


def jaro(a: str, b: str) -> float:
    """Return Jaro similarity as a 0-1 score."""
    if a == b:
        return 1.0

    len_a, len_b = len(a), len(b)
    if len_a == 0 or len_b == 0:
        return 0.0

    match_distance = max(max(len_a, len_b) // 2 - 1, 0)
    a_matches = [False] * len_a
    b_matches = [False] * len_b
    matches = 0

    for i, char_a in enumerate(a):
        lo = max(0, i - match_distance)
        hi = min(i + match_distance + 1, len_b)
        for j in range(lo, hi):
            if b_matches[j] or char_a != b[j]:
                continue
            a_matches[i] = True
            b_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    a_sequence = [a[i] for i in range(len_a) if a_matches[i]]
    b_sequence = [b[j] for j in range(len_b) if b_matches[j]]
    transpositions = sum(1 for char_a, char_b in zip(a_sequence, b_sequence) if char_a != char_b)

    return (
        matches / len_a
        + matches / len_b
        + (matches - transpositions / 2) / matches
    ) / 3


def jaro_score(a: str, b: str) -> float:
    """Return Jaro similarity as a 0-100 score."""
    return round(jaro(a, b) * 100, 1)


def jaro_winkler_score(a: str, b: str, p: float = 0.1) -> float:
    """Return Jaro-Winkler similarity as a 0-100 score.

    Jaro-Winkler gives a small bonus for a shared prefix up to four characters.
    """
    jaro_value = jaro(a, b)
    prefix = 0

    for i in range(min(len(a), len(b), 4)):
        if a[i] != b[i]:
            break
        prefix += 1

    return round((jaro_value + prefix * p * (1 - jaro_value)) * 100, 1)


ScoreFunction = Callable[[str, str], float]

ALGOS: dict[str, ScoreFunction] = {
    "levenshtein": levenshtein_score,
    "jaro": jaro_score,
    "jaro_winkler": jaro_winkler_score,
}


# ── Presentation helpers ─────────────────────────────────────────────────────

def highlight(candidate: str, query: str, *, color: bool = True) -> str:
    """Highlight candidate characters that also appear in the query."""
    c = palette(color)
    query_chars = set(query.casefold())
    output = []

    for char in candidate:
        if char.casefold() in query_chars:
            output.append(f"{c['bold']}{c['cyan']}{char}{c['reset']}")
        else:
            output.append(char)

    return "".join(output)


def score_bar(score: float, width: int = 20, *, color: bool = True, unicode: bool = True) -> str:
    """Render a compact score bar."""
    c = palette(color)
    filled = int(score / 100 * width)
    full, empty = ("█", "░") if unicode else ("#", "-")

    if score >= 80:
        bar_color = c["green"]
    elif score >= 50:
        bar_color = c["yellow"]
    else:
        bar_color = c["red"]

    return f"{bar_color}{full * filled}{empty * (width - filled)}{c['reset']}"


# ── Input loading ─────────────────────────────────────────────────────────────

def detect_delimiter(lines: Sequence[str], col: int) -> str | None:
    """Detect tab/comma delimited input, or return None for plain text.

    Column 1 can still be CSV/TSV. This matters for rows such as
    `id,name,email`, where `--col 1` should return `id`, not the whole line.
    """
    sample = "\n".join(lines[:5])

    if "\t" in sample:
        return "\t"

    if "," in sample:
        return ","

    if col > 1:
        # Let users pass `--col 2` for a comma-separated stream even when the
        # first few lines happen to contain no comma. Rows without the column
        # are safely skipped below.
        return ","

    return None


def load_words(source: io.TextIOBase, col: int) -> list[str]:
    """Load candidate words from plain text, CSV, or TSV input."""
    lines = source.read().splitlines()
    if not lines:
        return []

    delimiter = detect_delimiter(lines, col)
    if delimiter is None:
        return [line.strip() for line in lines if line.strip()]

    words: list[str] = []
    reader = csv.reader(lines, delimiter=delimiter)
    for row in reader:
        if len(row) < col:
            continue
        value = row[col - 1].strip()
        if value:
            words.append(value)

    return words


# ── CLI parsing ───────────────────────────────────────────────────────────────

def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")

    return parsed


def column_number(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError("must be 1 or greater")

    return parsed


def threshold_score(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc

    if parsed < 0 or parsed > 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")

    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fuzzy string matcher using Levenshtein / Jaro / Jaro-Winkler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
        add_help=False,
    )
    parser.add_argument("query", help="Query string to match against")
    parser.add_argument("file", nargs="?", help="Word list file; default: stdin")
    parser.add_argument("-n", "--top", type=positive_int, default=10, metavar="N")
    parser.add_argument("-t", "--threshold", type=threshold_score, default=0.0, metavar="N")
    parser.add_argument(
        "-a",
        "--algo",
        default="levenshtein",
        choices=sorted(ALGOS.keys()),
        metavar="ALGO",
    )
    parser.add_argument("-c", "--col", type=column_number, default=1, metavar="N")
    parser.add_argument("-i", "--ignore-case", action="store_true")
    parser.add_argument("--csv", action="store_true", help="Output results as CSV")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("-h", "--help", action="help", help="Show this help")
    return parser.parse_args(argv)


# ── Main ──────────────────────────────────────────────────────────────────────

def read_candidates(args: argparse.Namespace) -> list[str]:
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as file:
            return load_words(file, args.col)

    if sys.stdin.isatty():
        raise RuntimeError(
            "no file given and stdin is a terminal. "
            "Pipe a word list or pass a filename. Run with -h for help."
        )

    return load_words(sys.stdin, args.col)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    stdout_color = sys.stdout.isatty() and not args.no_color and not args.csv
    stdout_unicode = supports_pretty_glyphs(sys.stdout)
    stderr_color = sys.stderr.isatty() and not args.no_color
    out = palette(stdout_color)
    err = palette(stderr_color)

    try:
        words = read_candidates(args)
    except FileNotFoundError:
        print(f"{err['red']}Error:{err['reset']} file not found: {args.file}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"{err['red']}Error:{err['reset']} {exc}", file=sys.stderr)
        return 1

    if not words:
        print(f"{err['yellow']}Warning:{err['reset']} word list is empty.", file=sys.stderr)
        return 0

    query = args.query
    score_fn = ALGOS[args.algo]

    if args.ignore_case:
        normalized_query = query.casefold()
        scored = [(word, score_fn(normalized_query, word.casefold())) for word in words]
    else:
        scored = [(word, score_fn(query, word)) for word in words]

    results = [(word, score) for word, score in scored if score >= args.threshold]
    results.sort(key=lambda item: item[1], reverse=True)
    results = results[: args.top]

    if not results:
        print(f"{out['yellow']}No matches above threshold {args.threshold}.{out['reset']}")
        return 0

    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["rank", "score", "match"])
        for rank, (word, score) in enumerate(results, 1):
            writer.writerow([rank, f"{score:.1f}", word])
        return 0

    algo_label = args.algo.replace("_", "-")
    print(
        f"\n  {out['bold']}fuzzy match{out['reset']}  "
        f"query={out['cyan']}{query}{out['reset']}  "
        f"algo={out['dim']}{algo_label}{out['reset']}  "
        f"words={out['dim']}{len(words):,}{out['reset']}  "
        f"showing={out['dim']}{len(results)}{out['reset']}\n"
    )

    rank_width = len(str(len(results)))
    score_width = 6
    bar_width = 20
    max_word_length = max(len(word) for word, _ in results)
    column_width = max(max_word_length, 6)

    header = f"  {'#':>{rank_width}}  {'score':>{score_width}}  {'bar':<{bar_width + 10}}  match"
    print(f"{out['dim']}{header}{out['reset']}")
    separator = "─" if stdout_unicode else "-"
    print(f"  {separator * rank_width}  {separator * score_width}  {separator * bar_width}  {separator * column_width}")

    for rank, (word, score) in enumerate(results, 1):
        bar = score_bar(score, bar_width, color=stdout_color, unicode=stdout_unicode)
        highlighted = highlight(word, query, color=stdout_color)
        rank_text = f"{rank:>{rank_width}}"
        score_text = f"{score:>{score_width}.1f}"

        if rank == 1:
            rank_text = f"{out['bold']}{out['green']}{rank_text}{out['reset']}"
        elif rank <= 3:
            rank_text = f"{out['yellow']}{rank_text}{out['reset']}"

        print(f"  {rank_text}  {score_text}  {bar}  {highlighted}")

    print()
    best_word, best_score = results[0]
    print(
        f"  {out['bold']}Best match:{out['reset']} {out['cyan']}{best_word}{out['reset']} "
        f"({out['green']}{best_score:.1f}{out['reset']}/100)\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
