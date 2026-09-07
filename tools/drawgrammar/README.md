# DrawGrammar container

A container image with the [DrawGrammar](https://github.com/jacquev6/DrawGrammar)
command-line tool, `draw_grammar`, which renders railroad diagrams from
ISO-14977 EBNF. It is the tool the course's syntax-diagram (DS) images are
made with; [`tools/gen_ds.py`](../gen_ds.py) drives it to turn an EBNF key
(`compiler_testing_lib/syntax/<version>/ebnf-<language>.txt`) into the PNG
served by `compiler-tester` at `/ds?version=…`.

## Why a container

DrawGrammar is an OCaml program with no published binaries, and its opam
packages (`DrawGrammar`, `General`, `JsOfOCairo`) were removed from the live
opam repository in 2024. They still exist in
[`opam-repository-archive`](https://github.com/ocaml/opam-repository-archive),
and `JsOfOCairo 2.0.0` requires `js_of_ocaml-compiler < 3.4`, i.e. OCaml < 4.08.
The Dockerfile therefore starts from `ocaml/opam:debian-12-ocaml-4.07`, adds the
archive repository and installs `DrawGrammar.0.2.2`. The full DejaVu font set is
installed so non-terminals render in italics like the original images.

## Build (once)

```bash
podman build -t drawgrammar tools/drawgrammar     # or: docker build -t drawgrammar tools/drawgrammar
```

The image is ~3 GB (OCaml toolchain); the build takes a few minutes.

## Use

Through the generator (the normal path):

```bash
python3 tools/gen_ds.py v2.1 go -o out/ \
    --draw-grammar "podman run --rm --userns=keep-id -v .:/work:Z -w /work localhost/drawgrammar"
# -> out/H06DS.png
```

Directly, on any ISO-EBNF file in the current directory (the PNG is written
next to the input as `<file>.png`):

```bash
podman run --rm --userns=keep-id -v .:/work:Z -w /work localhost/drawgrammar \
    --syntax iso-ebnf --ignore DIGIT,LETTER my_grammar.iso-ebnf
podman run --rm localhost/drawgrammar --help     # all options (fonts, spacing, --inline, ...)
```

With Docker instead of podman, drop `--userns=keep-id` and `:Z`, and pass
`--user "$(id -u):$(id -g)"` if your uid is not 1000.

## Gotchas

- **`--userns=keep-id` is required with rootless podman.** Without it the
  container's `opam` user maps to a subuid, the mounted directory is not
  writable, and `draw_grammar` dies with `Cairo.Error(WRITE_ERROR)`.
- The mounted directory must be the one that holds the input file: the tool
  writes the PNG next to the input and only sees `/work`.
- DrawGrammar reads strict ISO-14977: `ε` is not accepted (use an empty
  alternative), bare digits/letters/`...` must be quoted, comments are
  `(* ... *)`. `gen_ds.py` applies exactly these rewrites to the course keys.

## Alternative without OCaml

The author also publishes a js_of_ocaml build of the same code
(`docs/draw_grammar_js.bc.js`, used by the online demo). Driven by headless
Chromium it produces the same diagrams; `gen_ds.py` accepts any command via
`--draw-grammar`, so such a wrapper can replace this image if needed.
