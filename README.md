# Fuzzy Match CLI

A small zero-dependency Python command-line tool for finding the closest matching strings in a word list.

It supports three fuzzy matching algorithms:

- **Levenshtein** similarity for typo-tolerant matching
- **Jaro** similarity for short strings and names
- **Jaro-Winkler** similarity for names and strings where the beginning is important

The tool can read candidates from a file or from standard input, supports plain text, CSV, and TSV input, and can print either a readable terminal table or CSV output for scripts.

## Features

- Reads from a file or `stdin`
- Supports plain word lists, CSV, and TSV input
- Selects a specific CSV/TSV column with `--col`
- Supports case-insensitive matching
- Supports score thresholds from `0` to `100`
- Supports machine-readable CSV output
- Pretty terminal output with score bars and highlighted characters


## Installation

### Option 1: Run as a standalone script

Clone the repository and run the script directly:

```bash
git clone https://github.com/andrii2g/fuzzy-match-cli.git
cd fuzzy-match-cli
python3 fuzzy.py "pytohn" words.txt
```

You can also make it executable:

```bash
chmod +x fuzzy.py
./fuzzy.py "pytohn" words.txt
```

### Option 2: Put it somewhere on your PATH

```bash
sudo cp fuzzy.py /usr/local/bin/fuzzy
sudo chmod +x /usr/local/bin/fuzzy
```

Then run:

```bash
fuzzy "pytohn" words.txt
```

## Usage

```text
fuzzy.py <query> [options] [wordlist_file]
```

If no file is provided, the tool reads candidates from standard input.

```text
Options:
  -n, --top N          Show top N matches. Default: 10
  -t, --threshold N    Only show matches with score >= N. Range: 0-100. Default: 0
  -a, --algo ALGO      Algorithm: levenshtein, jaro, or jaro_winkler. Default: levenshtein
  -c, --col N          Use column N, 1-based, for CSV/TSV input. Default: 1
  -i, --ignore-case    Match case-insensitively
  --csv                Output results as CSV
  -h, --help           Show help
```

## Examples

### Match a typo against a word list

```bash
./fuzzy.py "pytohn" words.txt
```

### Show only the top 5 matches

```bash
./fuzzy.py "pytohn" words.txt --top 5
```

### Use Jaro-Winkler for name-like matching

```bash
./fuzzy.py "Jon Smith" names.txt --algo jaro_winkler
```

### Ignore case

```bash
./fuzzy.py "nginx" /etc/hosts --ignore-case
```

### Read candidates from stdin

```bash
cat words.txt | ./fuzzy.py "helo wrold"
```

### Match against the second column in a CSV file

```bash
cat names.csv | ./fuzzy.py "Jon Smith" --col 2 --threshold 70
```

### Produce CSV output

```bash
./fuzzy.py "pytohn" words.txt --csv
```

Example output:

```csv
rank,score,match
1,83.3,python
2,66.7,pylon
3,50.0,typhoon
```

## Input formats

### Plain text

One candidate per line:

```text
python
pytorch
pytest
pylint
```

### CSV

```csv
id,name
1,John Smith
2,Jane Smith
3,Jon Smyth
```

To match against the second column:

```bash
./fuzzy.py "Jon Smith" names.csv --col 2
```

### TSV

```text
1	John Smith
2	Jane Smith
3	Jon Smyth
```

The tool auto-detects tab-separated input when tabs are present.

## Algorithm guide

### Levenshtein

Best default choice for typo correction and general string distance.

Example use cases:

- Misspelled words
- Command names
- File names
- Configuration keys

### Jaro

Good for short strings where character transpositions matter less than exact edit distance.

Example use cases:

- Short labels
- Names
- Codes

### Jaro-Winkler

Good for names and identifiers where a shared prefix should increase the score.

Example use cases:

- Person names
- Company names
- Product names
- Hostnames with common prefixes

## Exit behavior

- If the input file does not exist, the tool prints an error and exits with code `1`.
- If no file is provided and stdin is interactive, the tool prints an error and exits with code `1`.
- If the word list is empty, the tool prints a warning and exits successfully.
- If no matches pass the threshold, the tool prints a message and exits successfully.

## Performance notes

The tool is intentionally simple and dependency-free.

Current behavior:

- It loads the full input into memory.
- It scores every candidate.
- It sorts all scored candidates and returns the top results.

This is perfectly fine for small and medium word lists. For very large files, a future version could use streaming input plus `heapq.nlargest()` to keep only the best `N` matches in memory.

## Suggested repository structure

```text
fuzzy-match-cli/
├── fuzzy.py
├── README.md
├── LICENSE
├── CHANGELOG.md
├── .gitignore
├── pyproject.toml
├── tests/
│   ├── test_algorithms.py
│   └── test_cli.py
└── .github/
    └── workflows/
        └── ci.yml
```

## Development

Run the script locally:

```bash
python3 fuzzy.py "pytohn" words.txt
```

Run tests:

```bash
python3 -m pytest
```

Format and lint the code if development tools are configured:

```bash
python3 -m ruff check .
python3 -m ruff format .
```

## Recommended improvements before publishing

The current script is already useful, but a few small hardening changes would make it better for a public repository:

1. Validate CLI arguments:
   - `--top` should be greater than `0`
   - `--threshold` should be between `0` and `100`
   - `--col` should be greater than or equal to `1`

2. Improve CSV detection:
   - Currently comma-separated input is parsed as CSV only when `--col` is greater than `1`.
   - For CSV files where the desired column is `1`, the current implementation may treat the whole line as plain text.

3. Use `casefold()` instead of `lower()` for better Unicode-aware case-insensitive matching.

4. Disable ANSI colors automatically when stdout is not a terminal, or support a `--no-color` option.

5. Add automated tests for algorithms, input loading, CLI validation, and CSV output.

## License

MIT License.
