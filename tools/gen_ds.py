#!/usr/bin/env python3
"""Render the syntax diagrams (DS) for a version/language straight from its
EBNF key, so the diagram can never drift from what ebnfcheck grades.

    python3 tools/gen_ds.py v2.1 go -o out/            # -> out/H06DS.svg (+ .png if inkscape is on PATH)
    python3 tools/gen_ds.py v2.0 go -o out/ --name my.svg

Source of truth: compiler_testing_lib/syntax/<version>/ebnf-<lang>.txt.
The diagram speaks the lexer's vocabulary, so a small presentation table
maps grammar names to the token/short names used by the course images
(PROGRAM -> PROGR, NUMBER -> INT terminal, DIGIT/LETTER dropped ...).

Requires: pip install railroad-diagrams ; optional: inkscape (PNG export).
"""
from __future__ import annotations

import argparse, html, io, os, re, shutil, subprocess, sys
from railroad import (Diagram, Sequence, Choice, ZeroOrMore, OneOrMore, Terminal,
                      NonTerminal, Skip, Start, End, DiagramItem, Path, DEFAULT_STYLE)

# --- presentation: grammar vocabulary -> diagram vocabulary --------------------
RENAME = {"PROGRAM": "PROGR", "STATEMENT": "STMT", "BOOLEXPRESSION": "BEXPR",
          "BOOLTERM": "BTERM", "RELEXPRESSION": "REXPR", "EXPRESSION": "EXPR",
          "FUNCDEC": "FUNC", "VARDEC": "VARDEC"}
LEXICAL = {"NUMBER": "INT", "IDENTIFIER": "IDEN", "STRING": "STR", "BOOLEAN": "BOOL"}  # rule -> token
DROP = {"DIGIT", "LETTER"} | set(LEXICAL)      # lexer-level rules: not drawn
H_NUMBER = {"v1.0": "H02", "v1.1": "H03", "v1.2": "H04", "v2.0": "H05",
            "v2.1": "H06", "v2.2": "H07", "v3.0": "H08", "v2.3": "H09"}

# --- EBNF parsing (same surface syntax as the keys / ebnfcheck) ---------------
def ebnf_tokens(text):
    text = re.sub(r"//.*?$", "", text, flags=re.M)
    toks, i = [], 0
    while i < len(text):
        c = text[i]
        if c.isspace(): i += 1; continue
        if c in "{}[]()|,=;": toks.append(("sym", c)); i += 1; continue
        if c in "\"'":
            j = text.index(c, i + 1); toks.append(("lit", text[i + 1:j])); i = j + 1; continue
        j = i
        while j < len(text) and not text[j].isspace() and text[j] not in "{}[]()|,=;": j += 1
        toks.append(("id", text[i:j])); i = j
    return toks

def parse_ebnf(text):
    """-> ordered {rule: node}; node = ('alt'|'seq', [..]) | ('rep'|'opt', node) | ('lit'|'ref', str)"""
    toks, pos, rules = ebnf_tokens(text), 0, {}
    def peek(): return toks[pos] if pos < len(toks) else (None, None)
    def take():
        nonlocal pos; t = toks[pos]; pos += 1; return t
    def alt():
        seqs = [seq()]
        while peek() == ("sym", "|"): take(); seqs.append(seq())
        return ("alt", seqs) if len(seqs) > 1 else seqs[0]
    def seq():
        items = []
        while True:
            k, v = peek()
            if k is None or (k == "sym" and v in "|)]};"): break
            if k == "sym" and v == ",": take(); continue
            items.append(atom())
        return ("seq", items)
    def atom():
        k, v = take()
        if k == "sym" and v == "(": n = alt(); assert take() == ("sym", ")"); return n
        if k == "sym" and v == "{": n = alt(); assert take() == ("sym", "}"); return ("rep", n)
        if k == "sym" and v == "[": n = alt(); assert take() == ("sym", "]"); return ("opt", n)
        if k == "lit": return ("lit", v)
        if v in ("ε", "λ"): return ("seq", [])
        return ("ref", v)
    while pos < len(toks):
        _, name = take(); assert take() == ("sym", "="), name
        rules[name] = alt(); assert take() == ("sym", ";"), name
    return rules

# --- EBNF AST -> railroad items -----------------------------------------------
def is_empty(n): return n[0] == "seq" and not n[1]

def build(n):
    kind, val = n
    if kind == "lit":
        return Terminal(val.replace("\\n", "\\n"))
    if kind == "ref":
        if val in LEXICAL: return Terminal(LEXICAL[val])
        return NonTerminal(RENAME.get(val, val))
    if kind == "alt":
        # ε goes on the main line (as in the course images), the rest below
        empties = [a for a in val if is_empty(a)]; rest = [a for a in val if not is_empty(a)]
        items = ([Skip()] if empties else []) + [build(a) for a in rest]
        return Choice(0, *items) if len(items) > 1 else items[0]
    if kind == "opt":
        return Choice(0, Skip(), build(val))
    if kind == "rep":
        return ZeroOrMore(build(val))
    if kind == "seq":
        if not val: return Skip()
        out, i = [], 0
        while i < len(val):
            item, nxt = val[i], val[i + 1] if i + 1 < len(val) else None
            # X, { sep..., X }  ->  OneOrMore(X, sep)   (how EXPR/TERM/BEXPR are drawn)
            if nxt and nxt[0] == "rep" and nxt[1][0] == "seq" and nxt[1][1] and nxt[1][1][-1] == item:
                sep = nxt[1][1][:-1]
                out.append(OneOrMore(build(item), build(("seq", sep)) if sep else None)); i += 2; continue
            out.append(build(item)); i += 1
        return out[0] if len(out) == 1 else Sequence(*out)
    raise ValueError(kind)

# --- rendering in the style of the existing course images ---------------------
class DotStart(Start):
    def format(self, x, y, width):
        DiagramItem("circle", attrs={"cx": x + 4, "cy": y, "r": 4, "class": "dot"}).addTo(self)
        Path(x + 8, y).right(self.width - 8).addTo(self); return self

class RingEnd(End):
    def __init__(self):
        DiagramItem.__init__(self, "g"); self.width = 20; self.up = 10; self.down = 10
    def format(self, x, y, width):
        Path(x, y).right(self.width - 8).addTo(self)
        DiagramItem("circle", attrs={"cx": x + self.width - 4, "cy": y, "r": 4, "class": "ring"}).addTo(self); return self

STYLE = re.sub(r"svg\.railroad-diagram text \{.*?\}", "svg.railroad-diagram text{text-anchor:middle;white-space:pre}",
               DEFAULT_STYLE, flags=re.S) + """
svg.railroad-diagram path{stroke-width:2;fill:none}
svg.railroad-diagram rect{stroke-width:2;fill:#fff}
svg.railroad-diagram circle.dot{fill:#000}
svg.railroad-diagram circle.ring{fill:#fff;stroke:#000;stroke-width:2}
.label{font:16px sans-serif;fill:#000}
"""
FONT = 'font-family="DejaVu Sans Mono, monospace" font-size="14"'

def render_svg(rules):
    LABEL_H, GAP, PAD = 22, 14, 6
    parts, y, width = [], PAD, 0
    for name, body in rules.items():
        if name in DROP: continue
        d = Diagram(DotStart(), build(body), RingEnd()).format()
        buf = io.StringIO(); d.writeSvg(buf.write); svg = buf.getvalue()
        # explicit fonts on text (Inkscape ignores descendant selectors / shorthand cascade)
        svg = re.sub(r'(<g class="non-terminal[^"]*">.*?<text)', rf'\1 {FONT} font-style="italic" font-weight="normal"', svg, flags=re.S)
        svg = re.sub(r'(<g class="terminal[^"]*">.*?<text)', rf'\1 {FONT} font-weight="bold"', svg, flags=re.S)
        w = float(re.search(r'width="([\d.]+)"', svg).group(1)); h = float(re.search(r'height="([\d.]+)"', svg).group(1))
        parts.append(f'<text x="{PAD}" y="{y + 15}" class="label">{html.escape(RENAME.get(name, name))}:</text>')
        parts.append(f'<g transform="translate({PAD},{y + LABEL_H})">{svg}</g>')
        y += LABEL_H + h + GAP; width = max(width, w + 2 * PAD)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{y}" viewBox="0 0 {width} {y}">'
            f'<style>{STYLE}</style><rect width="100%" height="100%" fill="white"/>{"".join(parts)}</svg>')

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version"); ap.add_argument("language")
    ap.add_argument("-o", "--outdir", default="."); ap.add_argument("--name", help="output basename (default H0xDS)")
    ap.add_argument("--no-png", action="store_true")
    a = ap.parse_args(argv)
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "compiler_testing_lib", "syntax")
    key = os.path.join(root, a.version, f"ebnf-{a.language.lower()}.txt")
    rules = parse_ebnf(open(key).read())
    base = a.name or f"{H_NUMBER.get(a.version, a.version)}DS"
    os.makedirs(a.outdir, exist_ok=True)
    svg_path = os.path.join(a.outdir, f"{base}.svg")
    open(svg_path, "w").write(render_svg(rules)); print(svg_path)
    if not a.no_png and shutil.which("inkscape"):
        png = svg_path[:-4] + ".png"
        subprocess.run(["inkscape", svg_path, "--export-type=png", f"--export-filename={png}",
                        "--export-background=white", "--export-dpi=96"], check=True, capture_output=True)
        print(png)

if __name__ == "__main__":
    main()
