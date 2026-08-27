#!/usr/bin/env python3
import argparse, os, re, shlex, shutil, subprocess, sys

H_NUMBER = {"v1.0": "H02", "v1.1": "H03", "v1.2": "H04", "v2.0": "H05",
            "v2.1": "H06", "v2.2": "H07", "v3.0": "H08", "v2.3": "H09"}
LEXICAL_RULES = "DIGIT,LETTER,NUMBER,IDENTIFIER"
BARE = r"(?<![\w\"'.])(?:[0-9]|[A-Za-z]|\.\.\.)(?![\w\"'.])"


def to_iso_ebnf(key):
    iso = re.sub(r"//(.*)$", r"(*\1 *)", key, flags=re.M)
    iso = re.sub(r"(?<!\w)[ελ](?!\w)", "", iso)
    rules = set(re.findall(r"^\s*(\w+)\s*=", iso, flags=re.M))
    return re.sub(BARE, lambda m: m.group(0) if m.group(0) in rules else f'"{m.group(0)}"', iso)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("language")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--name")
    ap.add_argument("--draw-grammar", default=os.environ.get("DRAW_GRAMMAR", "draw_grammar"))
    ap.add_argument("--ignore", default=LEXICAL_RULES)
    ap.add_argument("--keep-iso", action="store_true")
    a = ap.parse_args(argv)

    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "compiler_testing_lib", "syntax")
    key_path = os.path.join(root, a.version, f"ebnf-{a.language.lower()}.txt")
    base = a.name or f"{H_NUMBER.get(a.version, a.version)}DS"
    os.makedirs(a.outdir, exist_ok=True)
    iso_path = os.path.join(a.outdir, f"{base}.iso-ebnf")
    with open(key_path) as f, open(iso_path, "w") as out:
        out.write(to_iso_ebnf(f.read()))

    cmd = shlex.split(a.draw_grammar) + ["--syntax", "iso-ebnf", "--ignore", a.ignore, os.path.basename(iso_path)]
    proc = subprocess.run(cmd, cwd=a.outdir, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        return proc.returncode
    png = os.path.join(a.outdir, f"{base}.png")
    shutil.move(iso_path + ".png", png)
    if not a.keep_iso:
        os.remove(iso_path)
    print(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
