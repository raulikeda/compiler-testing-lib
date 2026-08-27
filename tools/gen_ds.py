#!/usr/bin/env python3
"""Render the syntax diagram (DS) of a version/language key with DrawGrammar.

    python3 tools/gen_ds.py v2.1 go -o out/            # -> out/H06DS.png
    python3 tools/gen_ds.py v2.1 go -o out/ --draw-grammar "podman run --rm --userns=keep-id -v .:/work:Z -w /work localhost/drawgrammar"

Source of truth: compiler_testing_lib/syntax/<version>/ebnf-<lang>.txt.
The key is rewritten to strict ISO-14977 (the only dialect DrawGrammar reads)
and fed to the `draw_grammar` CLI (https://github.com/jacquev6/DrawGrammar,
`opam install DrawGrammar`, or the container image in tools/drawgrammar/ — see its README).

The three differences between the course keys and ISO-14977:
  ε / λ                     ->  empty alternative        ("ε" is not ASCII)
  0 | 1 | ... | 9 (bare)    ->  "0" | "1" | "..." | "9"  (bare integers are only legal as `3 * X`)
  // comment                ->  (* comment *)            (`/` is an alternation symbol)
Lexical rules (DIGIT, LETTER, NUMBER, IDENTIFIER) are not drawn (--ignore).
"""
from __future__ import annotations

import argparse, os, re, shlex, shutil, subprocess, sys

H_NUMBER = {"v1.0": "H02", "v1.1": "H03", "v1.2": "H04", "v2.0": "H05",
            "v2.1": "H06", "v2.2": "H07", "v3.0": "H08", "v2.3": "H09"}
LEXICAL_RULES = "DIGIT,LETTER,NUMBER,IDENTIFIER"


def to_iso_ebnf(key: str) -> str:
    """Rewrite a course EBNF key as ISO-14977 (see module docstring)."""
    iso = re.sub(r"//(.*)$", r"(*\1 *)", key, flags=re.M)
    iso = re.sub(r"(?<!\w)[ελ](?!\w)", "", iso)
    # bare single letters/digits and '...' are terminals (DIGIT/LETTER lists) unless they name a rule
    rules = set(re.findall(r"^\s*(\w+)\s*=", iso, flags=re.M))
    bare = r"(?<![\w\"'.])(?:[0-9]|[A-Za-z]|\.\.\.)(?![\w\"'.])"
    iso = re.sub(bare, lambda m: m.group(0) if m.group(0) in rules else f'"{m.group(0)}"', iso)
    return iso


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version"); ap.add_argument("language")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--name", help="output basename (default: H0xDS by version)")
    ap.add_argument("--draw-grammar", default=os.environ.get("DRAW_GRAMMAR", "draw_grammar"),
                    help="draw_grammar command (default: $DRAW_GRAMMAR or 'draw_grammar' on PATH)")
    ap.add_argument("--ignore", default=LEXICAL_RULES, help=f"rules not to draw (default: {LEXICAL_RULES})")
    ap.add_argument("--keep-iso", action="store_true", help="keep the intermediate .iso-ebnf file")
    a = ap.parse_args(argv)

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "compiler_testing_lib", "syntax")
    key_path = os.path.join(root, a.version, f"ebnf-{a.language.lower()}.txt")
    base = a.name or f"{H_NUMBER.get(a.version, a.version)}DS"
    os.makedirs(a.outdir, exist_ok=True)
    iso_path = os.path.join(a.outdir, f"{base}.iso-ebnf")
    with open(key_path) as f, open(iso_path, "w") as out:
        out.write(to_iso_ebnf(f.read()))

    # draw_grammar writes <input>.png next to the input; run it from outdir so containers can mount "."
    cmd = shlex.split(a.draw_grammar) + ["--syntax", "iso-ebnf", "--ignore", a.ignore, os.path.basename(iso_path)]
    proc = subprocess.run(cmd, cwd=a.outdir, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr); return proc.returncode
    png = os.path.join(a.outdir, f"{base}.png")
    shutil.move(iso_path + ".png", png)
    if not a.keep_iso:
        os.remove(iso_path)
    print(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
