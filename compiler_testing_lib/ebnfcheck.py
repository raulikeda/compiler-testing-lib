import re
from typing import Dict, List, Tuple
import json
import os

SPECIAL = set("{}[]()|,=;")

def strip_comments(s: str) -> str:
    # remove //... and #... comments
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"#.*?$", "", s, flags=re.MULTILINE)
    return s

def split_rules(ebnf: str) -> List[str]:
    ebnf = strip_comments(ebnf).strip()
    # split by ';' but keep only non-empty
    parts = [p.strip() for p in ebnf.split(";")]
    return [p for p in parts if p]

def tokenize(rhs: str) -> List[str]:
    tokens: List[str] = []
    i = 0
    while i < len(rhs):
        c = rhs[i]
        if c.isspace():
            i += 1
            continue
        if c in SPECIAL:
            tokens.append(c)
            i += 1
            continue
        # string literal "..."
        if c == '"':
            j = i + 1
            while j < len(rhs) and rhs[j] != '"':
                # naive (no escapes) - enough for course grammars
                j += 1
            if j >= len(rhs):
                # unmatched quote; keep rest
                lit = rhs[i:]
                tokens.append(lit)
                break
            tokens.append(rhs[i:j+1])
            i = j + 1
            continue
        # identifier / number / ellipsis
        j = i
        while j < len(rhs) and (not rhs[j].isspace()) and (rhs[j] not in SPECIAL):
            j += 1
        tok = rhs[i:j]
        tokens.append(tok)
        i = j
    return tokens

def normalize_ident(tok: str) -> str:
    # keep string literals as-is
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        return tok
    # normalize ellipsis token
    if tok == "...":
        return "..."
    # normalize digits tokens (0..9) remain same
    if re.fullmatch(r"\d+", tok):
        return tok
    # identifiers -> UPPERCASE (so number == NUMBER)
    return tok.upper()

def expand_digit_ellipsis(tokens: List[str]) -> List[str]:
    # Convert: 0 | 1 | ... | 9  => 0|1|2|3|4|5|6|7|8|9
    # Works when pattern exists anywhere in token list.
    out: List[str] = []
    i = 0
    while i < len(tokens):
        # Look for: <d0> | <d1> | ... | <d9>
        if (i + 8 < len(tokens)
            and re.fullmatch(r"\d", tokens[i])
            and tokens[i+1] == "|"
            and re.fullmatch(r"\d", tokens[i+2])
            and tokens[i+3] == "|"
            and tokens[i+4] == "..."
            and tokens[i+5] == "|"
            and re.fullmatch(r"\d", tokens[i+6])):
            # We won't assume exact endpoints; only handle 0..9 case safely
            d0 = tokens[i]
            d_last = tokens[i+6]
            if d0 == "0" and d_last == "9":
                out.extend(["0","|","1","|","2","|","3","|","4","|","5","|","6","|","7","|","8","|","9"])
                i += 7
                continue
        out.append(tokens[i])
        i += 1
    return out

def normalize_paren_alternations(tokens: List[str]) -> List[str]:
    # For each (...) region, if it contains '|' at depth 0 INSIDE those parens,
    # sort the top-level alternatives.
    out: List[str] = []
    i = 0

    while i < len(tokens):
        if tokens[i] != "(":
            out.append(tokens[i])
            i += 1
            continue

        # extract until matching ')'
        start = i
        depth = 0
        j = i
        while j < len(tokens):
            if tokens[j] == "(":
                depth += 1
            elif tokens[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(tokens):
            # unmatched, just dump rest
            out.extend(tokens[i:])
            break

        inner = tokens[i+1:j]  # inside (...)
        # split by '|' at depth 0 within inner (consider nested ()[]{} too)
        alts: List[List[str]] = []
        cur: List[str] = []
        d = 0
        for t in inner:
            if t in ("(", "{", "["):
                d += 1
            elif t in (")", "}", "]"):
                d -= 1
            if t == "|" and d == 0:
                alts.append(cur)
                cur = []
            else:
                cur.append(t)
        alts.append(cur)

        if len(alts) > 1:
            # sort alternatives by their string form
            alts_sorted = sorted(alts, key=lambda a: "".join(a))
            rebuilt: List[str] = []
            for k, a in enumerate(alts_sorted):
                if k > 0:
                    rebuilt.append("|")
                rebuilt.extend(a)
            out.append("(")
            out.extend(rebuilt)
            out.append(")")
        else:
            out.extend(tokens[start:j+1])

        i = j + 1

    return out

def parse_rule(statement: str) -> Tuple[str, str]:
    # statement: LHS = RHS
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$", statement)
    if not m:
        raise ValueError(f"Invalid rule statement: {statement!r}")
    lhs = m.group(1).upper()
    rhs = m.group(2)
    return lhs, rhs

def canonicalize_rhs(rhs: str) -> str:
    toks = tokenize(rhs)
    toks = [normalize_ident(t) for t in toks]
    toks = expand_digit_ellipsis(toks)
    toks = normalize_paren_alternations(toks)
    return "".join(toks)

def canonicalize_ebnf(ebnf: str) -> Dict[str, str]:
    rules = {}
    for st in split_rules(ebnf):
        lhs, rhs = parse_rule(st)
        rules[lhs] = canonicalize_rhs(rhs)
    return rules

def compare_to_key(student_ebnf: str, key_ebnf: str) -> Tuple[bool, List[str]]:
    stu = canonicalize_ebnf(student_ebnf)
    key = canonicalize_ebnf(key_ebnf)

    errors: List[str] = []
    for rule, rhs_key in key.items():
        if rule not in stu:
            errors.append(f"Missing rule: {rule}")
            continue
        if stu[rule] != rhs_key:
            errors.append(f"Rule differs: {rule}\n  expected: {rhs_key}\n  got:      {stu[rule]}")
    ok = (len(errors) == 0)
    return ok, errors

def load_and_compare(readme: str, ebnf_model: str) -> Tuple[bool, List[str]]:

    # get text inside ```ebnf and ``` markers using regex
    m = re.search(r"```ebnf\s*(.*?)\s*```", readme, re.DOTALL)
    if not m:
        return False, ["No EBNF code block found in README."]
    ebnf = m.group(1)

    try:
        ok, errors = compare_to_key(ebnf, ebnf_model)
        return ok, errors
    except Exception as e:
        return False, [f"Error parsing EBNF: {str(e)}"]

if __name__ == "__main__":

    ebnf_ex = """Um texto qualquer

    ```ebnf
    EXPRESSION = TERM, { ("+" | "-"), TERM } ;
    TERM = FACTOR, { ("*" | "/"), FACTOR } ;
    FACTOR = ("+" | "-"), FACTOR | "(", EXPRESSION, ")" | NUMBER ;
    NUMBER = DIGIT, {DIGIT} ;
    DIGIT = 0 | 1 | ... | 9 ;
    ```

    Outro texto qualquer
    """

    ebnf_alt = """```ebnf
    EXPRESSION = TERM, { ("+" | "-"), TERM } ;
    TERM = FACTOR, { ("*" | "/"), FACTOR } ;
    NUMBER = DIGIT, {DIGIT} ;
    FACTOR = ("+" | "-"), FACTOR | "(", EXPRESSION, ")" | NUMBER ;
    DIGIT = 0 | 1 | ... | 9 ;
    ```"""

    ebnf_err = """```ebnf
    EXPR = TERM, { ("+" | "-"), TERM } ;
    TERM = FACTOR, { ("*" | "/"), FACTOR } ;
    FACTOR = ("+" | "-"), FACTOR | "(", EXPRESION, ")" | NUMBER ;
    ```"""

    # print(compare_to_key(ebnf_ex, ebnf_gab))
    print(load_and_compare(ebnf_ex, "v1.1"))
    print(load_and_compare(ebnf_alt, "v1.1"))
    print(load_and_compare(ebnf_err, "v1.1"))

    print(load_and_compare(ebnf_err, "v1.2"))