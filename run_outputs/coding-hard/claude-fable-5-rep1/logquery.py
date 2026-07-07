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
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_"
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
        ch = query[i]
        if ch.isspace():
            i += 1
        elif ch == "(":
            tokens.append(("lparen",))
            i += 1
        elif ch == ")":
            tokens.append(("rparen",))
            i += 1
        elif ch in "><":
            if i + 1 < n and query[i + 1] == "=":
                tokens.append(("op", ch + "="))
                i += 2
            else:
                tokens.append(("op", ch))
                i += 1
        elif ch == "=":
            tokens.append(("op", "="))
            i += 1
        elif ch == "!":
            if i + 1 < n and query[i + 1] == "=":
                tokens.append(("op", "!="))
                i += 2
            else:
                raise ValueError("unexpected character %r at position %d" % (ch, i))
        elif ch == '"':
            i += 1
            parts = []
            while True:
                if i >= n:
                    raise ValueError("unterminated quoted string")
                c = query[i]
                if c == "\\" and i + 1 < n and query[i + 1] == '"':
                    parts.append('"')
                    i += 2
                elif c == '"':
                    i += 1
                    break
                else:
                    parts.append(c)
                    i += 1
            tokens.append(("word", "".join(parts)))
        elif ch in _WORD_CHARS:
            start = i
            while i < n and query[i] in _WORD_CHARS:
                i += 1
            text = query[start:i]
            if text.lower() in _KEYWORDS:
                tokens.append(("kw", text.lower()))
            else:
                tokens.append(("word", text))
        else:
            raise ValueError("unexpected character %r at position %d" % (ch, i))
    return tokens


def parse(tokens):
    """Parse a token list into an AST built from tuples:
      ("or", left, right)  ("and", left, right)  ("not", child)
      ("cmp", field, op, value)
    Precedence: NOT > AND > OR; parentheses group. Raises ValueError on
    syntax errors, including trailing tokens and empty input."""
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        tok = peek()
        if tok is None:
            raise ValueError("unexpected end of query")
        pos[0] += 1
        return tok

    def parse_or():
        node = parse_and()
        while peek() == ("kw", "or"):
            advance()
            node = ("or", node, parse_and())
        return node

    def parse_and():
        node = parse_not()
        while peek() == ("kw", "and"):
            advance()
            node = ("and", node, parse_not())
        return node

    def parse_not():
        if peek() == ("kw", "not"):
            advance()
            return ("not", parse_not())
        return parse_atom()

    def parse_atom():
        tok = advance()
        if tok == ("lparen",):
            node = parse_or()
            if advance() != ("rparen",):
                raise ValueError("expected ')'")
            return node
        if tok[0] == "word":
            op = advance()
            if op[0] != "op":
                raise ValueError("expected comparison operator, got %r" % (op,))
            value = advance()
            if value[0] != "word":
                raise ValueError("expected value, got %r" % (value,))
            return ("cmp", tok[1], op[1], value[1])
        raise ValueError("unexpected token %r" % (tok,))

    ast = parse_or()
    if pos[0] != len(tokens):
        raise ValueError("trailing tokens: %r" % (tokens[pos[0]:],))
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
    _, field, op, value = ast
    if field not in record:
        return False
    left = record[field]
    try:
        left, right = float(left), float(value)
    except (TypeError, ValueError):
        left, right = str(left), value
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
    return left <= right


def run_query(records, query):
    """Return the records matching the query string (provided helper)."""
    ast = parse(tokenize(query))
    return [r for r in records if match(r, ast)]


def aggregate(records, field):
    """Count records by the value of `field`. Records missing the field are
    skipped. Returns a dict mapping value -> count."""
    counts = {}
    for record in records:
        if field in record:
            value = record[field]
            counts[value] = counts.get(value, 0) + 1
    return counts


def top_n(records, field, n):
    """Return the n most common values of `field` as (value, count) tuples,
    ordered by count descending, ties broken by value ascending (string
    order)."""
    counts = aggregate(records, field)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return ordered[:n]
