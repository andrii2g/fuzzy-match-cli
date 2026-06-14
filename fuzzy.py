#!/usr/bin/env python3
"""
fuzzy.py — Levenshtein / Jaro-Winkler fuzzy string matcher

Usage:
    fuzzy.py <query> [options] [wordlist_file]

    If no file is given, reads the word list from stdin (one word per line).

Options:
    -n, --top N          Show top N matches (default: 10)
    -t, --threshold N    Only show matches with score >= N (0–100, default: 0)
    -a, --algo ALGO      Algorithm: levenshtein | jaro | jaro_winkler (default: levenshtein)
    -c, --col N          Use column N (1-based) if input is CSV/TSV (default: 1)
    -i, --ignore-case    Case-insensitive matching
    --csv                Output results as CSV
    -h, --help           Show this help

Examples:
    fuzzy.py "helo wrold" words.txt
    fuzzy.py "pytohn" words.txt -n 5 -a jaro_winkler
    cat names.csv | fuzzy.py "Jon Smith" -c 2 --threshold 70
    fuzzy.py "nginx" /etc/hosts -i
"""

import argparse
import csv
import io
import sys

# ── ANSI colours ──────────────────────────────────────────────────────────────
RESET  = "\x1b[0m"
BOLD   = "\x1b[1m"
DIM    = "\x1b[2m"
GREEN  = "\x1b[32m"
YELLOW = "\x1b[33m"
CYAN   = "\x1b[36m"
RED    = "\x1b[31m"
BLUE   = "\x1b[34m"

# ── Algorithms (zero dependencies) ────────────────────────────────────────────

def levenshtein(a: str, b: str) -> int:
    """Classic Wagner-Fischer DP algorithm. O(m·n) time, O(min(m,n)) space."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Keep only two rows
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr[j] = min(
                prev[j] + 1,       # deletion
                curr[j - 1] + 1,   # insertion
                prev[j - 1] + cost # substitution
            )
        prev = curr
    return prev[-1]


def levenshtein_score(a: str, b: str) -> float:
    """Normalise edit distance to a 0–100 similarity score."""
    dist = levenshtein(a, b)
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 100.0
    return round((1 - dist / max_len) * 100, 1)


def jaro(a: str, b: str) -> float:
    """Jaro similarity. Returns 0–1."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    match_dist = max(la, lb) // 2 - 1
    match_dist = max(0, match_dist)
    a_matches = [False] * la
    b_matches = [False] * lb
    matches = 0
    transpositions = 0
    for i in range(la):
        lo = max(0, i - match_dist)
        hi = min(i + match_dist + 1, lb)
        for j in range(lo, hi):
            if b_matches[j] or a[i] != b[j]:
                continue
            a_matches[i] = b_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    a_seq = [a[i] for i in range(la) if a_matches[i]]
    b_seq = [b[j] for j in range(lb) if b_matches[j]]
    for ca, cb in zip(a_seq, b_seq):
        if ca != cb:
            transpositions += 1
    return (matches / la + matches / lb +
            (matches - transpositions / 2) / matches) / 3


def jaro_score(a: str, b: str) -> float:
    return round(jaro(a, b) * 100, 1)


def jaro_winkler_score(a: str, b: str, p: float = 0.1) -> float:
    """Jaro-Winkler gives a bonus for shared prefixes (up to 4 chars)."""
    j = jaro(a, b)
    prefix = 0
    for i in range(min(len(a), len(b), 4)):
        if a[i] == b[i]:
            prefix += 1
        else:
            break
    return round((j + prefix * p * (1 - j)) * 100, 1)


ALGOS = {
    "levenshtein":  levenshtein_score,
    "jaro":         jaro_score,
    "jaro_winkler": jaro_winkler_score,
}

# ── Highlight matching substrings ─────────────────────────────────────────────

def highlight(candidate: str, query: str) -> str:
    """Bold any characters in candidate that also appear in query (rough visual aid)."""
    query_chars = set(query.lower())
    out = []
    for ch in candidate:
        if ch.lower() in query_chars:
            out.append(f"{BOLD}{CYAN}{ch}{RESET}")
        else:
            out.append(ch)
    return "".join(out)


def score_bar(score: float, width: int = 20) -> str:
    filled = int(score / 100 * width)
    if score >= 80:
        color = GREEN
    elif score >= 50:
        color = YELLOW
    else:
        color = RED
    return f"{color}{'█' * filled}{'░' * (width - filled)}{RESET}"

# ── Input loading ─────────────────────────────────────────────────────────────

def load_words(source: io.TextIOBase, col: int) -> list[str]:
    """Load words from a file-like object. Auto-detects CSV/TSV vs plain text."""
    lines = source.read().splitlines()
    if not lines:
        return []
    # Detect delimiter
    sample = "\n".join(lines[:5])
    if "\t" in sample:
        delim = "\t"
    elif "," in sample and col > 1:
        delim = ","
    else:
        # Plain word list — just strip and return
        if col == 1:
            return [ln.strip() for ln in lines if ln.strip()]
        delim = ","

    words = []
    reader = csv.reader(lines, delimiter=delim)
    for row in reader:
        if len(row) >= col:
            val = row[col - 1].strip()
            if val:
                words.append(val)
    return words

# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Fuzzy string matcher using Levenshtein / Jaro / Jaro-Winkler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
        add_help=False,
    )
    p.add_argument("query",              help="Query string to match against")
    p.add_argument("file", nargs="?",   help="Word list file (default: stdin)")
    p.add_argument("-n", "--top",        type=int, default=10,           metavar="N")
    p.add_argument("-t", "--threshold",  type=float, default=0,          metavar="N")
    p.add_argument("-a", "--algo",       default="levenshtein",
                   choices=list(ALGOS.keys()),                            metavar="ALGO")
    p.add_argument("-c", "--col",        type=int, default=1,            metavar="N")
    p.add_argument("-i", "--ignore-case", action="store_true")
    p.add_argument("--csv",              action="store_true")
    p.add_argument("-h", "--help",       action="help")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Load word list
    try:
        if args.file:
            with open(args.file, encoding="utf-8", errors="replace") as f:
                words = load_words(f, args.col)
        else:
            if sys.stdin.isatty():
                print(f"{RED}Error:{RESET} no file given and stdin is a terminal.\n"
                      "       Pipe a word list or pass a filename.\n"
                      "       Run with -h for help.", file=sys.stderr)
                sys.exit(1)
            words = load_words(sys.stdin, args.col)
    except FileNotFoundError:
        print(f"{RED}Error:{RESET} file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if not words:
        print(f"{YELLOW}Warning:{RESET} word list is empty.", file=sys.stderr)
        sys.exit(0)

    query = args.query
    score_fn = ALGOS[args.algo]

    if args.ignore_case:
        q = query.lower()
        scored = [(w, score_fn(q, w.lower())) for w in words]
    else:
        scored = [(w, score_fn(query, w)) for w in words]

    # Filter, sort, trim
    scored = [(w, s) for w, s in scored if s >= args.threshold]
    scored.sort(key=lambda x: x[1], reverse=True)
    results = scored[: args.top]

    if not results:
        print(f"{YELLOW}No matches above threshold {args.threshold}.{RESET}")
        return

    # ── CSV output ────────────────────────────────────────────────────────────
    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["rank", "score", "match"])
        for rank, (word, score) in enumerate(results, 1):
            writer.writerow([rank, score, word])
        return

    # ── Pretty terminal output ────────────────────────────────────────────────
    algo_label = args.algo.replace("_", "-")
    print(f"\n  {BOLD}fuzzy match{RESET}  "
          f"query={CYAN}{query}{RESET}  "
          f"algo={DIM}{algo_label}{RESET}  "
          f"words={DIM}{len(words):,}{RESET}  "
          f"showing={DIM}{len(results)}{RESET}\n")

    rank_w  = len(str(len(results)))
    score_w = 6
    bar_w   = 20
    max_word_len = max(len(w) for w, _ in results)
    col_w   = max(max_word_len, 6)

    header = (f"  {'#':>{rank_w}}  {'score':>{score_w}}  "
              f"{'bar':<{bar_w + 10}}  {'match'}")
    print(f"{DIM}{header}{RESET}")
    print(f"  {'─' * rank_w}  {'─' * score_w}  {'─' * bar_w}  {'─' * col_w}")

    for rank, (word, score) in enumerate(results, 1):
        bar     = score_bar(score, bar_w)
        hl      = highlight(word, query)
        rank_s  = f"{rank:>{rank_w}}"
        score_s = f"{score:>{score_w}.1f}"
        # rank colour
        if rank == 1:
            rank_s = f"{BOLD}{GREEN}{rank_s}{RESET}"
        elif rank <= 3:
            rank_s = f"{YELLOW}{rank_s}{RESET}"
        print(f"  {rank_s}  {score_s}  {bar}  {hl}")

    print()
    best_word, best_score = results[0]
    print(f"  {BOLD}Best match:{RESET} {CYAN}{best_word}{RESET} "
          f"({GREEN}{best_score}{RESET}/100)\n")


if __name__ == "__main__":
    main()