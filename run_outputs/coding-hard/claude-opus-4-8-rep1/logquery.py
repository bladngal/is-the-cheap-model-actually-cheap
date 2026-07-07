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


_KEYWORDS = {"and", "or", "not"}
# Characters allowed in a bare word: letters, digits, and . : - _
_WORD_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_"
)


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
        # Operators: order matters so multi-char forms win over single-char.
        if c == "!":
            if query[i : i + 2] == "!=":
                tokens.append(("op", "!="))
                i += 2
                continue
            raise ValueError(f"unexpected character {c!r} at {i}")
        if c == "=":
            tokens.append(("op", "="))
            i += 1
            continue
        if c == ">":
            if query[i : i + 2] == ">=":
                tokens.append(("op", ">="))
                i += 2
            else:
                tokens.append(("op", ">"))
                i += 1
            continue
        if c == "<":
            if query[i : i + 2] == "<=":
                tokens.append(("op", "<="))
                i += 2
            else:
                tokens.append(("op", "<"))
                i += 1
            continue
        if c == '"':
            # Quoted string: consume until the closing quote, honoring \" and \\.
            i += 1
            chars = []
            closed = False
            while i < n:
                ch = query[i]
                if ch == "\\" and i + 1 < n:
                    nxt = query[i + 1]
                    if nxt in ('"', "\\"):
                        chars.append(nxt)
                        i += 2
                        continue
                    chars.append(ch)
                    i += 1
                    continue
                if ch == '"':
                    closed = True
                    i += 1
                    break
                chars.append(ch)
                i += 1
            if not closed:
                raise ValueError("unterminated quoted string")
            tokens.append(("word", "".join(chars)))
            continue
        if c in _WORD_CHARS:
            start = i
            while i < n and query[i] in _WORD_CHARS:
                i += 1
            text = query[start:i]
            lowered = text.lower()
            if lowered in _KEYWORDS:
                tokens.append(("kw", lowered))
            else:
                tokens.append(("word", text))
            continue
        raise ValueError(f"unexpected character {c!r} at {i}")
    return tokens


def parse(tokens):
    """Parse a token list into an AST built from tuples:
      ("or", left, right)  ("and", left, right)  ("not", child)
      ("cmp", field, op, value)
    Precedence: NOT > AND > OR; parentheses group. Raises ValueError on
    syntax errors, including trailing tokens and empty input."""
    pos = 0  # index into tokens, threaded through the helpers via nonlocal

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def advance():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_or():
        node = parse_and()
        while True:
            tok = peek()
            if tok is not None and tok == ("kw", "or"):
                advance()
                right = parse_and()
                node = ("or", node, right)
            else:
                return node

    def parse_and():
        node = parse_not()
        while True:
            tok = peek()
            if tok is not None and tok == ("kw", "and"):
                advance()
                right = parse_not()
                node = ("and", node, right)
            else:
                return node

    def parse_not():
        tok = peek()
        if tok is not None and tok == ("kw", "not"):
            advance()
            return ("not", parse_not())
        return parse_primary()

    def parse_primary():
        tok = peek()
        if tok is None:
            raise ValueError("unexpected end of input")
        if tok == ("lparen",):
            advance()
            node = parse_or()
            closing = peek()
            if closing != ("rparen",):
                raise ValueError("expected ')'")
            advance()
            return node
        # Otherwise expect a comparison: word op word
        if tok[0] != "word":
            raise ValueError(f"expected field name, got {tok!r}")
        field = advance()[1]
        op_tok = peek()
        if op_tok is None or op_tok[0] != "op":
            raise ValueError("expected comparison operator")
        op = advance()[1]
        val_tok = peek()
        if val_tok is None or val_tok[0] != "word":
            raise ValueError("expected value")
        value = advance()[1]
        return ("cmp", field, op, value)

    if not tokens:
        raise ValueError("empty query")
    ast = parse_or()
    if pos != len(tokens):
        raise ValueError(f"trailing tokens starting at {tokens[pos]!r}")
    return ast


def match(record, ast):
    """Evaluate an AST against a record and return True/False. A comparison
    on a field missing from the record is False (even for !=). If both sides
    of a comparison parse as floats, compare numerically; otherwise compare
    as strings."""
    kind = ast[0]
    if kind == "or":
        return match(record, ast[1]) or match(record, ast[2])
    if kind == "and":
        return match(record, ast[1]) and match(record, ast[2])
    if kind == "not":
        return not match(record, ast[1])
    if kind == "cmp":
        _, field, op, query_value = ast
        if field not in record:
            return False  # missing field is always False, even for !=
        return _compare(record[field], op, query_value)
    raise ValueError(f"unknown AST node {ast!r}")


def _try_float(x):
    """Return float(x) or None if it isn't parseable as a number."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _compare(record_value, op, query_value):
    """Compare a record value against a query value. Numeric when both parse
    as floats, otherwise lexicographic on their string forms."""
    left_num = _try_float(record_value)
    right_num = _try_float(query_value)
    if left_num is not None and right_num is not None:
        left, right = left_num, right_num
    else:
        left, right = str(record_value), str(query_value)

    if op == "=":
        return left == right
    if op == "!=":
        return left != right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    raise ValueError(f"unknown operator {op!r}")


def run_query(records, query):
    """Return the records matching the query string (provided helper)."""
    ast = parse(tokenize(query))
    return [r for r in records if match(r, ast)]


def aggregate(records, field):
    """Count records by the value of `field`. Records missing the field are
    skipped. Returns a dict mapping value -> count."""
    counts = {}
    for record in records:
        if field not in record:
            continue
        value = record[field]
        counts[value] = counts.get(value, 0) + 1
    return counts


def top_n(records, field, n):
    """Return the n most common values of `field` as (value, count) tuples,
    ordered by count descending, ties broken by value ascending (string
    order)."""
    counts = aggregate(records, field)
    # Sort by count descending, then by value ascending (string order) to
    # break ties deterministically.
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return ordered[:n]
