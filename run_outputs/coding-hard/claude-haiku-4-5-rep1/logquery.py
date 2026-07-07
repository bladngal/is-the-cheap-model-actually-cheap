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


def tokenize(query):
    """Return a list of token tuples:
    ("lparen",), ("rparen",), ("op", op), ("kw", "and"|"or"|"not"),
    ("word", text). Quoted strings become ("word", unescaped_text).
    Keywords are lowercased. Raises ValueError on any character that
    doesn't fit the language."""
    tokens = []
    i = 0
    while i < len(query):
        ch = query[i]
        if ch.isspace():
            i += 1
        elif ch == '(':
            tokens.append(("lparen",))
            i += 1
        elif ch == ')':
            tokens.append(("rparen",))
            i += 1
        elif ch == '"':
            # Parse quoted string
            i += 1
            s = ""
            while i < len(query):
                if query[i] == '"':
                    i += 1
                    break
                elif query[i] == '\\' and i + 1 < len(query) and query[i + 1] == '"':
                    s += '"'
                    i += 2
                else:
                    s += query[i]
                    i += 1
            tokens.append(("word", s))
        elif query[i:i+2] in ['!=', '>=', '<=']:
            tokens.append(("op", query[i:i+2]))
            i += 2
        elif ch in '=><':
            tokens.append(("op", ch))
            i += 1
        elif ch.isalpha() or ch.isdigit() or ch in '._:-':
            # Parse bare word (field name, number, or keyword)
            word = ""
            while i < len(query) and (query[i].isalnum() or query[i] in '._:-'):
                word += query[i]
                i += 1
            kw = word.lower()
            if kw in ('and', 'or', 'not'):
                tokens.append(("kw", kw))
            else:
                tokens.append(("word", word))
        else:
            raise ValueError(f"Invalid character: {ch}")
    return tokens


def parse(tokens):
    """Parse a token list into an AST built from tuples:
      ("or", left, right)  ("and", left, right)  ("not", child)
      ("cmp", field, op, value)
    Precedence: NOT > AND > OR; parentheses group. Raises ValueError on
    syntax errors, including trailing tokens and empty input."""
    if not tokens:
        raise ValueError("Empty input")

    pos = [0]  # Use list to allow modification in nested functions

    def peek():
        if pos[0] < len(tokens):
            return tokens[pos[0]]
        return None

    def consume():
        token = peek()
        pos[0] += 1
        return token

    def parse_or():
        left = parse_and()
        while peek() and peek()[0] == "kw" and peek()[1] == "or":
            consume()
            right = parse_and()
            left = ("or", left, right)
        return left

    def parse_and():
        left = parse_not()
        while peek() and peek()[0] == "kw" and peek()[1] == "and":
            consume()
            right = parse_not()
            left = ("and", left, right)
        return left

    def parse_not():
        if peek() and peek()[0] == "kw" and peek()[1] == "not":
            consume()
            child = parse_not()
            return ("not", child)
        return parse_primary()

    def parse_primary():
        token = peek()
        if not token:
            raise ValueError("Unexpected end of input")

        if token[0] == "lparen":
            consume()
            expr = parse_or()
            if not peek() or peek()[0] != "rparen":
                raise ValueError("Missing closing parenthesis")
            consume()
            return expr
        elif token[0] == "word":
            field = consume()[1]
            op_token = peek()
            if not op_token or op_token[0] != "op":
                raise ValueError("Expected operator")
            op = consume()[1]
            value_token = peek()
            if not value_token or value_token[0] != "word":
                raise ValueError("Expected value")
            value = consume()[1]
            return ("cmp", field, op, value)
        else:
            raise ValueError(f"Unexpected token: {token}")

    ast = parse_or()
    if pos[0] < len(tokens):
        raise ValueError("Trailing tokens")
    return ast


def match(record, ast):
    """Evaluate an AST against a record and return True/False. A comparison
    on a field missing from the record is False (even for !=). If both sides
    of a comparison parse as floats, compare numerically; otherwise compare
    as strings."""
    if ast[0] == "cmp":
        _, field, op, value = ast
        if field not in record:
            return False

        record_val = record[field]

        # Try to parse both as floats for numeric comparison
        try:
            record_num = float(record_val)
            value_num = float(value)
            # Both are numeric, compare numerically
            if op == "=":
                return record_num == value_num
            elif op == "!=":
                return record_num != value_num
            elif op == ">":
                return record_num > value_num
            elif op == ">=":
                return record_num >= value_num
            elif op == "<":
                return record_num < value_num
            elif op == "<=":
                return record_num <= value_num
        except (ValueError, TypeError):
            # At least one is not numeric, compare as strings
            record_str = str(record_val)
            value_str = str(value)
            if op == "=":
                return record_str == value_str
            elif op == "!=":
                return record_str != value_str
            elif op == ">":
                return record_str > value_str
            elif op == ">=":
                return record_str >= value_str
            elif op == "<":
                return record_str < value_str
            elif op == "<=":
                return record_str <= value_str

    elif ast[0] == "and":
        _, left, right = ast
        return match(record, left) and match(record, right)

    elif ast[0] == "or":
        _, left, right = ast
        return match(record, left) or match(record, right)

    elif ast[0] == "not":
        _, child = ast
        return not match(record, child)

    return False


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
            val = record[field]
            counts[val] = counts.get(val, 0) + 1
    return counts


def top_n(records, field, n):
    """Return the n most common values of `field` as (value, count) tuples,
    ordered by count descending, ties broken by value ascending (string
    order)."""
    counts = aggregate(records, field)
    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], str(x[0])))
    return sorted_items[:n]
