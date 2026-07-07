"""logquery — a tiny query engine for structured log records.

A log record is a dict of string keys to values (str, int, or float).

Query language:
  - Comparisons: field=value, field!=value, field>value, field>=value,
    field<value, field<=value
  - Values may be bare words (letters, digits, ., :, -, _) or double-quoted
    strings (which may contain spaces; \" escapes a quote).
  - Boolean operators (case-insensitive keywords): NOT binds tightest,
    then AND, then OR. Parentheses group.
  - Comparison semantics: if BOTH the record's field value and the query value
    can be parsed as floats, compare numerically; otherwise compare as strings.
  - A comparison on a field missing from the record is False (even for !=).

Public API (all must be implemented):
  tokenize(query)            -> list of tokens
  parse(tokens)              -> AST
  match(record, ast)         -> bool
  run_query(records, query)  -> list of matching records (provided)
  aggregate(records, field)  -> dict value -> count (records missing field skipped)
  top_n(records, field, n)   -> list of (value, count), count desc, ties by value asc
"""

_WORD_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:_-"
)
_KEYWORDS = {"and", "or", "not"}


def tokenize(query):
    """Return a list of token tuples:
    ("lparen",), ("rparen",), ("op", op), ("kw", "and"|"or"|"not"),
    ("word", text). Quoted strings become ("word", unescaped_text).
    Keywords are lowercased. Raises ValueError on any character that
    doesn't fit the language."""
    tokens = []
    i = 0
    n = len(query)
    while i < n:
        c = query[i]
        if c.isspace():
            i += 1
            continue
        if c == "(":
            tokens.append(("lparen",))
            i += 1
            continue
        if c == ")":
            tokens.append(("rparen",))
            i += 1
            continue
        if c == '"':
            i += 1
            chars = []
            while i < n and query[i] != '"':
                if query[i] == "\\" and i + 1 < n and query[i + 1] == '"':
                    chars.append('"')
                    i += 2
                else:
                    chars.append(query[i])
                    i += 1
            if i >= n:
                raise ValueError("unterminated quoted string")
            i += 1
            tokens.append(("word", "".join(chars)))
            continue
        if c == "!":
            if i + 1 < n and query[i + 1] == "=":
                tokens.append(("op", "!="))
                i += 2
                continue
            raise ValueError(f"bad character: {c!r}")
        if c == ">":
            if i + 1 < n and query[i + 1] == "=":
                tokens.append(("op", ">="))
                i += 2
            else:
                tokens.append(("op", ">"))
                i += 1
            continue
        if c == "<":
            if i + 1 < n and query[i + 1] == "=":
                tokens.append(("op", "<="))
                i += 2
            else:
                tokens.append(("op", "<"))
                i += 1
            continue
        if c == "=":
            tokens.append(("op", "="))
            i += 1
            continue
        if c in _WORD_CHARS:
            j = i
            while j < n and query[j] in _WORD_CHARS:
                j += 1
            text = query[i:j]
            low = text.lower()
            if low in _KEYWORDS:
                tokens.append(("kw", low))
            else:
                tokens.append(("word", text))
            i = j
            continue
        raise ValueError(f"bad character: {c!r}")
    return tokens


def parse(tokens):
    """Parse a token list into an AST built from tuples:
      ("or", left, right)  ("and", left, right)  ("not", child)
      ("cmp", field, op, value)
    Precedence: NOT > AND > OR; parentheses group. Raises ValueError on
    syntax errors, including trailing tokens and empty input."""
    if not tokens:
        raise ValueError("empty query")

    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def is_kw(tok, word):
        return tok is not None and tok[0] == "kw" and tok[1] == word

    def parse_or():
        left = parse_and()
        while is_kw(peek(), "or"):
            advance()
            right = parse_and()
            left = ("or", left, right)
        return left

    def parse_and():
        left = parse_not()
        while is_kw(peek(), "and"):
            advance()
            right = parse_not()
            left = ("and", left, right)
        return left

    def parse_not():
        if is_kw(peek(), "not"):
            advance()
            return ("not", parse_not())
        return parse_primary()

    def parse_primary():
        tok = peek()
        if tok is None:
            raise ValueError("unexpected end of input")
        if tok[0] == "lparen":
            advance()
            node = parse_or()
            tok2 = peek()
            if tok2 is None or tok2[0] != "rparen":
                raise ValueError("expected closing parenthesis")
            advance()
            return node
        if tok[0] == "word":
            field = advance()[1]
            optok = peek()
            if optok is None or optok[0] != "op":
                raise ValueError("expected comparison operator")
            op = advance()[1]
            valtok = peek()
            if valtok is None or valtok[0] != "word":
                raise ValueError("expected comparison value")
            value = advance()[1]
            return ("cmp", field, op, value)
        raise ValueError(f"unexpected token: {tok}")

    result = parse_or()
    if pos[0] != len(tokens):
        raise ValueError("trailing tokens")
    return result


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def match(record, ast):
    """Evaluate an AST against a record and return True/False. A comparison
    on a field missing from the record is False (even for !=). If both sides
    of a comparison parse as floats, compare numerically; otherwise compare
    as strings."""
    kind = ast[0]
    if kind == "and":
        return match(record, ast[1]) and match(record, ast[2])
    if kind == "or":
        return match(record, ast[1]) or match(record, ast[2])
    if kind == "not":
        return not match(record, ast[1])
    if kind == "cmp":
        field, op, value = ast[1], ast[2], ast[3]
        if field not in record:
            return False
        rec_val = record[field]
        rec_f = _as_float(rec_val)
        val_f = _as_float(value)
        if rec_f is not None and val_f is not None:
            a, b = rec_f, val_f
        else:
            a, b = str(rec_val), str(value)
        if op == "=":
            return a == b
        if op == "!=":
            return a != b
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        raise ValueError(f"unknown operator: {op}")
    raise ValueError(f"unknown ast node: {kind}")


def run_query(records, query):
    """Return the records matching the query string (provided helper)."""
    ast = parse(tokenize(query))
    return [r for r in records if match(r, ast)]


def aggregate(records, field):
    """Count records by the value of `field`. Records missing the field are
    skipped. Returns a dict mapping value -> count."""
    counts = {}
    for r in records:
        if field in r:
            v = r[field]
            counts[v] = counts.get(v, 0) + 1
    return counts


def top_n(records, field, n):
    """Return the n most common values of `field` as (value, count) tuples,
    ordered by count descending, ties broken by value ascending (string
    order)."""
    counts = aggregate(records, field)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return ordered[:n]
